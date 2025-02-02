FROM python:3.12.2-bookworm
RUN pip3 install flask flask_sqlalchemy pandas 

WORKDIR /app

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
CMD ["flask", "run"]
