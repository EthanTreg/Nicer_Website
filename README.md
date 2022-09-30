# Nicer Website
Website code to replace existing Nicer data interface website:  
https://nicer-web.mit.edu/nicerview/

## Requirements
* Install dependencies:  
`pip install -r requirements/prod.txt`
* Create new secret key:  
Create `.env` file under root directory  
Generate new secret key by running `generate_secret_key.py` and copying the output into the `.env` file
* Migrate database:  
Run `python manage.py migrate` in the terminal

## Running Website Locally
* Start website server:  
Run `python manage.py runserver` in the terminal
* Open website:  
In a web browser, go to `http://127.0.0.1:8000`

## Adding Data to the Database
* Configure database update script:  
Open `db_update.py` in a text editor and specify the path to the data under the variable `data_dir`
* Run `db_update.py` script
* Check website _Directory_ tab for the new data:  
If already on _Directory_, you will have to change to a different tab such as _Home_ and go back to _Directory_