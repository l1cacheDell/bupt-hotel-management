package handlers

import (
	"backend_go/db_utils"
	"backend_go/scheduler"

	"github.com/gin-gonic/gin"
)

type TurnOnOffRequest struct {
	RoomNumber int `json:"room_id"`
}

// TODO: 这里要进行逻辑检查，是否能够开启、关闭，如果已经开了或者已经关了就不能做同样的操作。

func TurnOn(c *gin.Context) {
	var req TurnOnOffRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}

	formatted_time := GetCurrentTime()

	sql := "UPDATE room_infos SET state = 1 WHERE room_id = ?"
	if err := db_utils.DB.Exec(sql, req.RoomNumber).Error; err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}
	sql = "INSERT INTO op_records (room_id, op_time, op_type, old, new) values (?, ?, ?, 0, 1)"
	operator_type := 1
	if err := db_utils.DB.Exec(sql, req.RoomNumber, formatted_time, operator_type).Error; err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}

	// send msg to scheduler
	msg := scheduler.SchedulerMsg{
		RoomID: req.RoomNumber,
		Types:  "add",
		Speed:  "medium",
	}
	scheduler.Sche.MsgChan <- &msg

	c.JSON(200, gin.H{"message": "turn on success"})
}

func TurnOff(c *gin.Context) {
	var req TurnOnOffRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}
	formatted_time := GetCurrentTime()

	sql := "UPDATE room_infos SET state = 0 WHERE room_id = ?"
	if err := db_utils.DB.Exec(sql, req.RoomNumber).Error; err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}
	sql = "INSERT INTO op_records (room_id, op_time, op_type, old, new) values (?, ?, ?, 1, 0)"
	operator_type := 1
	if err := db_utils.DB.Exec(sql, req.RoomNumber, formatted_time, operator_type).Error; err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		return
	}

	// send msg to scheduler
	msg := scheduler.SchedulerMsg{
		RoomID: req.RoomNumber,
		Types:  "delete",
		Speed:  "medium",
	}
	scheduler.Sche.MsgChan <- &msg

	c.JSON(200, gin.H{"message": "turn off success"})
}
