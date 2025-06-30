@echo off

start cmd /k "cd be && uvicorn main:app"

timeout /t 3 >nul

cd fe
mvn javafx:run

