@echo off
title 🔁 Đang chạy Backend (FastAPI)
start cmd /k "cd be && uvicorn main:app --reload"

timeout /t 3

title 🖥️ Đang chạy Frontend (JavaFX)
cd fe
mvn javafx:run