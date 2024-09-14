package handlers

var Record int = 0

func NextRecord() int {
	tmp := Record
	Record++
	return tmp
}
