package scheduler

import (
	"backend_go/db_utils"
	"container/list"
	"fmt"
	"log"
	"sync"
	"time"
)

// Scheduler is a single instance, which cannot be created twice.
// In the lifespan of the program, there will be only one scheduler.
type SchedulerMsg struct {
	RoomID int
	Types  string // 'add', 'update', 'delete'
	Speed  string // 'low', 'medium', 'high'
}

type Scheduler struct {
	RoomCount   int
	ServingSize int
	MsgChan     chan *SchedulerMsg
	EleChan     chan *ScheElement
}

type Slot struct {
	RoomID int
	Start  time.Time // time is used to recording the serving time, because it will be preempted by others
	Speed  int       // 1: low, 2: medium, 3: high
}

type ScheElement struct {
	list_e          *list.Element
	generate_detail bool
}

// The design of this package is: scheduler can be created through `InitSche()` function,
// and the global variable `Sche` will be instantiated in this package.
// And after instantiate the `Sche`, it will start a goroutine to run the scheduler, and the scheduler
// will receive the update operation from the channel `Sche.UpdateChan`, and update the corresponding
// field of the `ScheduleBody` struct.
var Sche *Scheduler // public, global variable

// the essential data structure of the scheduler, private
var scheMutex sync.Mutex
var waiting_queue *list.List
var running_queue *list.List

// ===================== structure method field =====================
func (s *Scheduler) Start() {
	go func() {
		for msg := range s.MsgChan {
			s.recvMsg(msg)
		}
	}()

	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				s.step()
			}
		}
	}()

	go func() {
		for e := range s.EleChan {
			s.collect(e)
		}
	}()
}

func (s *Scheduler) step() {
	fmt.Println("schedule")
	if waiting_queue.Len() == 0 && running_queue.Len() == 0 {
		return
	}
	scheMutex.Lock()
	defer scheMutex.Unlock()

	if waiting_queue.Len() > 0 {
		if running_queue.Len() < s.ServingSize {
			first_e_wait := waiting_queue.Front()         // 自然进入
			first_e_wait.Value.(*Slot).Start = time.Now() // 开始设置时间，现在算作开始serving
			running_queue.PushBack(first_e_wait.Value)
			waiting_queue.Remove(first_e_wait)
		} else {
			first_e_run := running_queue.Front()
			first_e_wait := waiting_queue.Front()
			if first_e_wait.Value.(*Slot).Speed >= first_e_run.Value.(*Slot).Speed {
				running_queue.Remove(first_e_run)

				first_e_wait.Value.(*Slot).Start = time.Now() // 开始设置时间，现在算作开始serving
				running_queue.PushBack(first_e_wait.Value)
				waiting_queue.Remove(first_e_wait)

				// 只有元素从running queue中移除的时候，才进行schedule
				sche_ele := &ScheElement{
					list_e:          first_e_run,
					generate_detail: false,
				}
				s.EleChan <- sche_ele

				insertWaitingQueue(first_e_run.Value.(*Slot)) // 被抢占，重新进入等待队列
			}
		}
	} else {
		running_queue.MoveToBack(running_queue.Front())
	}

	// print list
	for e := running_queue.Front(); e != nil; e = e.Next() {
		fmt.Printf("running: %v\n", e.Value.(*Slot).RoomID)
	}
	for e := waiting_queue.Front(); e != nil; e = e.Next() {
		fmt.Printf("waiting: %v\n", e.Value.(*Slot).RoomID)
	}

}

func (s *Scheduler) collect(e *ScheElement) {
	// this function will only read the running_queue and waiting_queue, and update the database.
	// thus it is not necessary to lock the mutex.
	le := e.list_e
	if !e.generate_detail {
		start_time := le.Value.(*Slot).Start
		end_time := time.Now()
		duration := end_time.Sub(start_time)

		sql := "INSERT INTO scheduler_board (room_id, duration, speed, cost) values (?, ?, ?, ?)"
		cost := 26.3
		if err := db_utils.DB.Exec(sql, le.Value.(*Slot).RoomID, duration, le.Value.(*Slot).Speed, cost); err != nil {
			fmt.Println(err)
		}
	} else {
		now_time := time.Now()
		duration := now_time.Sub(le.Value.(*Slot).Start)

		sql := "SELECT cost FROM scheduler_board WHERE room_id = ?"
		var cost []float32
		if err := db_utils.DB.Raw(sql, le.Value.(*Slot).RoomID).Scan(&cost); err != nil {
			log.Println(err)
			return
		}
		var sum float32
		for _, c := range cost {
			sum += c
		}

		sum += float32(duration) * 1

		// delete all related records
		sql = "DELETE FROM scheduler_board WHERE room_id = ?"
		if err := db_utils.DB.Exec(sql, le.Value.(*Slot).RoomID); err != nil {
			log.Println(err)
			return
		}
	}
}

func (s *Scheduler) recvMsg(msg *SchedulerMsg) {
	// this function is responsible for converting msg to slot
	// and send it to waiting queue.
	scheMutex.Lock()
	defer scheMutex.Unlock()

	var slot *Slot
	var e *list.Element
	var place int
	for e = waiting_queue.Front(); e != nil; e = e.Next() {
		if e.Value.(*Slot).RoomID == msg.RoomID {
			slot = e.Value.(*Slot)
			place = 2
			break
		}
	}
	for e = running_queue.Front(); e != nil; e = e.Next() {
		if e.Value.(*Slot).RoomID == msg.RoomID {
			slot = e.Value.(*Slot)
			place = 1
			break
		}
	}

	if slot == nil {
		slot = &Slot{
			RoomID: msg.RoomID,
			Start:  time.Now(),
			Speed:  getSpeed(msg.Speed),
		}
		if msg.Types == "add" {
			insertWaitingQueue(slot)
		} else {
			fmt.Println("invalid operation")
		}
	} else {
		if msg.Types == "update" {
			slot.Speed = getSpeed(msg.Speed)
			e.Value.(*Slot).Speed = slot.Speed
		} else if msg.Types == "delete" {
			// TODO: notify the collect goroutine
			if place == 1 {
				running_queue.Remove(e)
			} else if place == 2 {
				waiting_queue.Remove(e)
			}
		}
		s.EleChan <- &ScheElement{
			list_e:          e,
			generate_detail: true,
		}
	}
	// The index of the slot depends on the speed.
}

func (s *Scheduler) Stop() {
	close(s.MsgChan)
}

// ===================== helper function field =====================
func getSpeed(speed string) int {
	switch speed {
	case "low":
		return 1
	case "medium":
		return 2
	case "high":
		return 3
	default:
		fmt.Println("invalid speed")
		return 1
	}
}

func insertWaitingQueue(slot *Slot) {
	// warning: this function must be executed after scheMutex is locked.

	if waiting_queue.Len() == 0 {
		waiting_queue.PushBack(slot)
	} else {
		var e *list.Element
		for e = waiting_queue.Front(); e != nil; e = e.Next() {
			if slot.Speed > e.Value.(*Slot).Speed {
				break // it will find the first slot with speed less than the new slot's speed
			}
		}
		if e != nil {
			waiting_queue.InsertBefore(slot, e)
		} else {
			waiting_queue.PushBack(slot)
		}
	}
}

func CreateScheduler(roomCount, servingSize, waitingSize int) *Scheduler {
	if servingSize+waitingSize > roomCount {
		return nil
	}
	waiting_queue = list.New()
	running_queue = list.New()
	return &Scheduler{
		RoomCount:   roomCount,
		ServingSize: servingSize,
		MsgChan:     make(chan *SchedulerMsg, servingSize*10), // 20 is the buffer size of the channel
		EleChan:     make(chan *ScheElement, servingSize*10),
	}
}

func InitSche(RoomTotal, ServingSize, WaitingSize int) {
	Sche = CreateScheduler(RoomTotal, ServingSize, WaitingSize)
	go Sche.Start()
} // offer an entrance for scheduler, and scheduler will work as a global variable, and run in a goroutine.
