
import pandas as pd
from flask import Flask, render_template, redirect, url_for, flash
from forms import LoginForm  # Assuming your form is in a file named forms.py
from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory, session
from forms import RegistrationForm, LoginForm
import mysql.connector

import torch
from transformers import VisionEncoderDecoderModel, ViTFeatureExtractor, AutoTokenizer
#from app import app
import os
from PIL import Image
print("packages loaded")
# import generate 
# Import your caption generation function

model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
print("mode loaded")
feature_extractor = ViTFeatureExtractor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
# tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
from transformers import ViTFeatureExtractor, AutoTokenizer

# Trying to initialize the tokenizer and log any issues directly
try:
    tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
    print("Tokenizer initialized successfully.")
    print("CLS token ID:", tokenizer.cls_token_id)
    print("SEP token ID:", tokenizer.sep_token_id)
except Exception as e:
    print("Failed to initialize tokenizer:", str(e))
    tokenizer = None



device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

max_length = 25
num_beams = 8
gen_kwargs = {"max_length": max_length, "num_beams": num_beams}


APP_ROOT=os.path.dirname(os.path.abspath(__file__))
app=Flask(__name__)
#app.secret_key="from infinity to beyond"
app.config['UPLOAD_FOLDER']=os.path.join(APP_ROOT, 'static/image/')
app.config['SECRET_KEY']='b0b4fbefdc48be27a6123605f02b6b86'
db = mysql.connector.connect(host="localhost", port=3306, user="root", password="", database="image_caption")
cur = db.cursor()


@app.route("/")
@app.route("/home")
def home():
    return render_template('index.html')

@app.route("/aboutus")
def aboutus():
    return render_template('aboutus.html')

@app.route("/ourproject")
def ourproject():
    return render_template('ourproject.html')

@app.route("/contact")
def contact():
    return render_template('contact.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        print(email,password)
        if email == 'admin@gmail.com' and password == "admin":
            session['loggedin'] = True
            session['admin'] = True
            flash("You have been logged in as the Administrator!", 'success')
            return redirect(url_for('ourproject'))
        else:
            # Your database logic here
            # Example: query the database to retrieve user information
            sql = "select * from register where email = '"+email+"' and password = '"+password+"' and status = 'accepted' "
            cur.execute(sql)
            data = cur.fetchall()
            db.commit()
            print(data)
            print("==================================")
            # Check if the user exists and the password is correct
            if len(data)>0:
                flash(f"Welcome {email}! You have been logged in.", 'success')
                return redirect(url_for('ourproject'))
            else:
                flash(f"No account with the email id {email} exists. Please register now.", 'info')
                return redirect(url_for('register'))

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('admin', None)
    return redirect(url_for('home'))

@app.route('/users')
def users():
    
    #Database connections
    db=mysql.connector.connect(host="localhost", port=3306, user="root", password="", db="image_caption")
    #Table as a data frame
    register=pd.read_sql_query('select * from {}'.format('register'), db)
    #Remove the password column
    register.drop(['password'], axis=1, inplace=True)

    return render_template('users.html', column_names=register.columns.values, row_data=list(register.values.tolist()))

@app.route("/users2/<int:id>", methods=['GET','POST'])
def users2(id=0):
    user_id=str(id)
    sql = "update register set status = 'accepted' where id = '%s'"%(user_id)
    cur.execute(sql)
    db.commit()
    return redirect(url_for('users'))

@app.route("/register", methods=['GET','POST'])
def register():
    form = RegistrationForm()
    #Database connection

    #Table as a data frame
    register=pd.read_sql_query('select * from {}'.format('register'), db)

    if form.validate_on_submit():
        email=form.email.data
        username = form.username.data
        password = form.password.data
        all_emails=register['email']
        if email in list(all_emails):
            flash('Account already exists with this Email Id! Please Log In.','warning')
            db.close()
            return redirect(url_for('login'))
        else:
            
            cur = db.cursor()
            sql = "INSERT INTO `register` (`username`,`email`,`password`) VALUES (%s, %s, %s)"
            val= (username,email,password)
            cur.execute(sql, val)
            db.commit()

            flash(f'Account Created for {form.username.data} Sucessfully! Please wait for the admin to verify your account.','success')

            return redirect(url_for('login'))
    return render_template('register.html', form=form)




def prepare_image(image_path):
    try:
        # Open the image file
        with Image.open(image_path) as img:
            # Convert the image to RGB
            img = img.convert("RGB")
            
            # Apply feature extraction
            pixel_values = feature_extractor(images=[img], return_tensors="pt").pixel_values
            
            # Move pixel values to the same device as model
            return pixel_values.to(device)
    except Exception as e:
        print(f"Failed to prepare image {image_path}: {e}")
        return None

def predict_captions(image_paths, num_captions=3):
    if tokenizer is None:
        print("Tokenizer is not initialized.")
        return []

    captions_list = []
    for image_path in image_paths:
        try:
            pixel_values = prepare_image(image_path)
            if pixel_values is None:
                continue

            captions = []
            # Generate multiple captions using different methods
            # Caption 1: Beam search with a smaller number of beams
            output_ids = model.generate(pixel_values, max_length=25, num_beams=5, early_stopping=True)
            captions.append(tokenizer.decode(output_ids[0], skip_special_tokens=True))

            # Caption 2: Random sampling with higher temperature for more creativity
            output_ids = model.generate(pixel_values, max_length=25, do_sample=True, top_k=50, temperature=0.9)
            captions.append(tokenizer.decode(output_ids[0], skip_special_tokens=True))

            # Caption 3: Nucleus sampling with a moderate top-p for a balance of relevance and variety
            output_ids = model.generate(pixel_values, max_length=25, do_sample=True, top_p=0.92, num_return_sequences=1)
            captions.append(tokenizer.decode(output_ids[0], skip_special_tokens=True))

            captions_list.append(captions)
        except Exception as e:
            print(f"Error processing {image_path}: {e}")

    return captions_list



@app.route("/upload", methods=["POST"])
def upload():
    target = os.path.join(APP_ROOT, 'static/image/')

    if not os.path.isdir(target):
        os.mkdir(target)
    file = request.files["myimage"]
    filename = file.filename

    if filename == "":
        flash('No File Selected', 'danger')
        return redirect(url_for('ourproject'))

    # Check if the file has a valid extension
    ext = os.path.splitext(filename)[1]
    if ext not in {".jpg", ".png"}:
        flash("Invalid Extensions! Please select a .jpg or a .png file only.", category="danger")
        return redirect(url_for('ourproject'))

    # Save the uploaded image
    destination = os.path.join(target, filename)
    file.save(destination)

    # Perform image captioning
    captions_list = predict_captions([destination])
    print("==========================")
    print(captions_list)
    print("==========================")
    
    # Render the "upload.html" template and pass data to it
    return render_template("upload.html", img_name=filename, captions_list=captions_list)


'''
# Function for image captioning
def predict_caption(image_paths):
    images = []
    for image_path in image_paths:
        i_image = Image.open(image_path)
        if i_image.mode != "RGB":
            i_image = i_image.convert(mode="RGB")

        images.append(i_image)

    pixel_values = feature_extractor(images=images, return_tensors="pt").pixel_values
    pixel_values = pixel_values.to(device)

    output_ids = model.generate(pixel_values, **gen_kwargs)

    preds = tokenizer.batch_decode(output_ids, skip_special_tokens=True)
    preds = [pred.strip() for pred in preds]
    return preds

from flask import render_template, redirect, url_for

# ...
@app.route("/upload", methods=["POST"])
def upload():
    target = os.path.join(APP_ROOT, 'static/image/')

    if not os.path.isdir(target):
        os.mkdir(target)
    file = request.files["myimage"]
    filename = file.filename

    if filename == "":
        flash('No File Selected', 'danger')
        return redirect(url_for('ourproject'))

    # Check if the file has a valid extension
    ext = os.path.splitext(filename)[1]
    if ext not in {".jpg", ".png"}:
        flash("Invalid Extensions! Please select a .jpg or a .png file only.", category="danger")
        return redirect(url_for('ourproject'))

    # Save the uploaded image
    destination = os.path.join(target, filename)
    file.save(destination)

    # Perform image captioning
    captions = predict_caption([destination])
    print(captions)
    
    # Render the "upload.html" template and pass data to it
    return render_template("upload.html",img_name=filename, captions=captions)
'''

@app.route('/upload/<filename>')
def send_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__=="__main__":
    app.run(debug=True)
