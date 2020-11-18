
APP_NAME=pyapputil

pylint:
	pylint --disable R,C,raise-missing-from $(APP_NAME)

dist:
	python setup.py dist

deploy: dist
	twine upload dist/$(APP_NAME)

clean:
	$(RM) --recursive dist $(APP_NAME).egg-info .cache
