// handlers/login.go
package handlers

import (
	"backend_go/db_utils"
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
)

type loginForm struct {
	Account  string `json:"account"`
	Password string `json:"password"`
}

func Login(c *gin.Context) {
	// 获取请求体
	var form loginForm
	if err := c.BindJSON(&form); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// 校验用户名和密码
	result, msg := db_utils.QueryUser(form.Account, form.Password)
	if !result {
		c.JSON(http.StatusUnauthorized, gin.H{"error": msg})
		return
	}

	// 登录成功
	identity := msg
	fmt.Println("Login successful")
	c.JSON(http.StatusOK, gin.H{"message": "Login successful", "identity": identity})
}
