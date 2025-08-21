run:
	python manage.py runserver

install:
	pip install -r requirements.txt

docker.compose.down:
	docker compose down --remove-orphans

docker.compose.run: docker.compose.down
	docker compose up -d --remove-orphans

docker.build:
	docker build -t suplements-store .
