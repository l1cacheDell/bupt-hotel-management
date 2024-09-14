package main

import (
	"backend_go/db_utils"
	"backend_go/routers"
	"backend_go/scheduler"
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
)

func main() {
	fmt.Println("Hello, world!")
	db_utils.Init_DB()
	scheduler.InitSche(40, 3, 2) // init here, scheduler will run in another goroutine
	defer scheduler.Sche.Stop()

	r := gin.Default()
	r.GET("/ping", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"message": "pong",
		})
	})

	routers.SetupRoutes(r)

	r.Run() // listen and serve on 0.0.0.0:8080 (for windows "localhost:8080")
}
