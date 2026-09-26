@echo off
echo Installing required dependencies...
pip install -r requirements.txt

echo.
echo Starting the AI Video Generator...
python -m streamlit run app.py

pause
