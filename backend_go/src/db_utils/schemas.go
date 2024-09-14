package db_utils

import "time"

type RoomInfo struct {
	RoomID         int       `gorm:"primary_key"`
	ClientID       string    `gorm:"type:varchar(255)"`
	ClientName     string    `gorm:"type:varchar(255)"`
	CheckinTime    time.Time `gorm:"type:datetime"`
	CheckoutTime   time.Time `gorm:"type:datetime"`
	State          int
	CurrentSpeed   string  `gorm:"type:varchar(255)"`
	CurrentTempera float32 `gorm:"type:float(7, 2)"`
}

type OpRecord struct {
	ID     int `gorm:"primary_key"`
	RoomID int
	OpTime time.Time `gorm:"type:datetime"`
	OpType int
	Old    string `gorm:"type:varchar(255)"`
	New    string `gorm:"type:varchar(255)"`
}

type Detail struct {
	ID        int `gorm:"primary_key"`
	RoomID    int
	QueryTime time.Time `gorm:"type:datetime"`
	StartTime time.Time `gorm:"type:datetime"`
	EndTime   time.Time `gorm:"type:datetime"`
	ServeTime float32   `gorm:"type:float(7, 2)"`
	Speed     string    `gorm:"type:varchar(255)"`
	Cost      float32   `gorm:"type:float(7, 2)"`
	Rate      float32   `gorm:"type:float(5, 2)"`
}

type User struct {
	Account  string `gorm:"primary_key;type:varchar(255)"`
	Password string `gorm:"type:varchar(255)"`
	Identity string `gorm:"type:varchar(255)"`
}

type SchedulerBoard struct {
	ID       int `gorm:"primary_key"`
	RoomID   int
	Duration float32 `gorm:"type:float(5, 2)"`
	Speed    string  `gorm:"type:varchar(255)"`
	Cost     float32 `gorm:"type:float(7, 2)"`
}
