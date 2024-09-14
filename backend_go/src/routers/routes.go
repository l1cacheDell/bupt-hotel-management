package routers

import (
	"backend_go/handlers"

	"github.com/gin-gonic/gin"
)

func SetupRoutes(router *gin.Engine) {
	api := router.Group("/api")
	{
		api.POST("/login", handlers.Login)
		api.POST("/rooms/checkIn", handlers.CheckIn)
		api.POST("/rooms/checkOut", handlers.CheckOut)
		api.POST("/turn_on", handlers.TurnOn)
		api.POST("/turn_off", handlers.TurnOff)
		api.POST("/setSpeed", handlers.SetSpeed)
		api.POST("/setTemperature", handlers.SetTempera)
	}
}
