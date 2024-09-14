package handlers

import (
	"backend_go/db_utils"
	"backend_go/scheduler"

	"github.com/gin-gonic/gin"
)

type SetSpeedRequest struct {
	RoomNumber int    `json:"room_id"`
	Speed      string `json:"speed"`
}

type SetTemperaRequest struct {
	RoomNumber int     `json:"room_id"`
	Tempera    float32 `json:"temperature"`
}

func SetSpeed(c *gin.Context) {
	var req SetSpeedRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	var old_speed string
	sql := "SELECT current_speed FROM room_infos WHERE room_id = ?"
	if result := db_utils.DB.Raw(sql, req.RoomNumber).Scan(&old_speed); result.RowsAffected == 0 {
		c.JSON(400, gin.H{
			"error": "room not found",
		})
		return
	}

	formatted_time := GetCurrentTime()
	operation_type := 3
	sql = "INSERT INTO op_records (room_id, op_time, op_type, old, new) values (?, ?, ?, ?, ?)"
	if err := db_utils.DB.Exec(sql, req.RoomNumber, formatted_time, operation_type, old_speed, req.Speed).Error; err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	sql = "UPDATE room_infos SET current_speed = ? WHERE room_id = ?"
	if err := db_utils.DB.Exec(sql, req.Speed, req.RoomNumber).Error; err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	// send msg to scheduler
	msg := scheduler.SchedulerMsg{
		RoomID: req.RoomNumber,
		Types:  "update",
		Speed:  req.Speed,
	}
	scheduler.Sche.MsgChan <- &msg

	// 设置上下文

	c.JSON(200, gin.H{
		"message": "success",
	})

}

func SetTempera(c *gin.Context) {
	var req SetTemperaRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	var old_tempera float32
	sql := "SELECT current_tempera FROM room_infos WHERE room_id = ?"
	if result := db_utils.DB.Raw(sql, req.RoomNumber).Scan(&old_tempera); result.RowsAffected == 0 {
		c.JSON(400, gin.H{
			"error": "room not found",
		})
		return
	}

	formatted_time := GetCurrentTime()
	operation_type := 2
	sql = "INSERT INTO op_records (room_id, op_time, op_type, old, new) values (?, ?, ?, ?, ?)"
	if err := db_utils.DB.Exec(sql, req.RoomNumber, formatted_time, operation_type, old_tempera, req.Tempera).Error; err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	sql = "UPDATE room_infos SET current_tempera = ? WHERE room_id = ?"
	if err := db_utils.DB.Exec(sql, req.Tempera, req.RoomNumber).Error; err != nil {
		c.JSON(400, gin.H{
			"error": err.Error(),
		})
		return
	}

	// 设置上下文

	c.JSON(200, gin.H{
		"message": "success",
	})
}
