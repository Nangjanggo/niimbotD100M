package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

func printHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req Request
	err := json.NewDecoder(r.Body).Decode(&req)
	if err != nil {
		setStatus(w, http.StatusBadRequest, "bad request")
		return
	}

	err = req.Validate()
	if err != nil {
		setStatus(w, http.StatusBadRequest, err.Error())
		return
	}

	err = PrintTag(req.Text, req.QrText)
	if err != nil {
		setStatus(w, http.StatusInternalServerError, err.Error())
		return
	}

	setStatus(w, http.StatusOK, "tag printed")
}

func setStatus(w http.ResponseWriter, code int, msg string) error {
	w.WriteHeader(code)
	return json.NewEncoder(w).Encode(&Response{Status: msg})
}

// Function for implementing Basic Authentication
func HandleAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		reqUsername, reqPassword, ok := r.BasicAuth()
		if !ok || reqUsername != os.Getenv("USERNAME") || reqPassword != os.Getenv("PASSWORD") {
			setStatus(w, http.StatusUnauthorized, "Wrong Credentials")
			return
		}
		next.ServeHTTP(w, r)
	})
}

func setupHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	var req SetupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		setStatus(w, http.StatusBadRequest, "bad request")
		return
	}
	if req.FridgeId == 0 || req.DeviceId == "" || req.Ec2Url == "" {
		setStatus(w, http.StatusBadRequest, "fridgeId, deviceId, ec2Url are required")
		return
	}

	username := os.Getenv("USERNAME")
	if username == "" { username = "admin" }
	password := os.Getenv("PASSWORD")
	if password == "" { password = "admin" }
	mac := os.Getenv("PRINTER_MAC")

	content := fmt.Sprintf(
		"USERNAME=%s\nPASSWORD=%s\nPRINTER_MAC=%s\nFRIDGE_ID=%d\nDEVICE_ID=%s\nEC2_URL=%s\n",
		username, password, mac, req.FridgeId, req.DeviceId, req.Ec2Url,
	)
	if err := os.WriteFile(".env", []byte(content), 0644); err != nil {
		setStatus(w, http.StatusInternalServerError, "failed to save config")
		return
	}
	setStatus(w, http.StatusOK, "setup complete")
}
