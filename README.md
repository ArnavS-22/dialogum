source venv/bin/activate && python -m gum.cli -u "Dhruv Yadati"
/Users/arnavsharma/gum-elicitation/venv/bin/python -m uvicorn dashboard.simple_api:app --host 0.0.0.0 --port 8000
cd dashboard && npm run dev