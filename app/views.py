from app import app

import os
from flask import flash, redirect, render_template, request, jsonify, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import pandas as pd
import io

from app.models import Users, Roles, Groups, Events, UserEvents, UserGroups
from app.utils import permission_admin#, login_required
from app.database import db_session, init_db, engine

login_manager_app=LoginManager(app)
login_manager_app.session_protection = "strong"
login_manager_app.login_view = "login"
login_manager_app.login_message_category = "info"

@login_manager_app.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

with app.app_context():
    init_db()
    # Check if roles already exist
    existing_roles = Roles.query.all()
    if not existing_roles:
        roles = ['admin', 'user']
        for role in roles:
            new_role = Roles(role=role)
            db_session.add(new_role)
        db_session.commit()
    # Check if user already exist
    existing_user = Users.query.all()
    if not existing_user:
        new_user = Users(name="admin", surname="admin", username="admin", hash=generate_password_hash("admin"), role_id=1)
        db_session.add(new_user)
        db_session.commit()

@app.route("/", methods=['GET'])
@login_required
def index():
    """
    Show list of events with same group id as user or None group id.
    """
    user_id = current_user.id
    role_id = current_user.role_id
    # if it is an admin, then show all events, no matter the group
    if role_id == 1:
        events = []
        for event in Events.query.all():
            events.append({
                'title': event.title,
                'groupId': event.group_id,
                'groupName': Groups.query.filter_by(id=event.group_id).first().name if Groups.query.filter_by(id=event.group_id).first() else None,
                'start': f"{event.date.strftime('%Y-%m-%d')} {event.start_time}",
                'end': f"{event.date.strftime('%Y-%m-%d')} {event.end_time}",
                'modalId': event.id,
                'description': event.description,
                'n_assistants': event.n_assistants,
                'backgroundColor': event.color if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else 'white',
                'borderColor': event.color,
                'textColor': 'black' if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else event.color
            })

        return render_template("index.html", events=events, user_id=user_id)

    else: # if user is not admin        
        usergroups = UserGroups.query.filter_by(user_id=user_id).all()
        events = []
        event_ids = set() # to avoid repetitions
        for usergroup in usergroups:
            events_by_group = Events.query.filter((Events.group_id == usergroup.group_id)).all()
            for event in events_by_group:
                if event.id not in event_ids:
                    events.append({
                        'title': event.title,
                        'groupId': event.group_id,
                        'groupName': Groups.query.filter_by(id=event.group_id).first().name if Groups.query.filter_by(id=event.group_id).first() else None,
                        'start': f"{event.date.strftime('%Y-%m-%d')} {event.start_time}",
                        'end': f"{event.date.strftime('%Y-%m-%d')} {event.end_time}",
                        'modalId': event.id,
                        'description': event.description,
                        'n_assistants': event.n_assistants,
                        'backgroundColor': event.color if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else 'white',
                        'borderColor': event.color,
                        'textColor': 'black' if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else event.color
                    })
                    event_ids.add(event.id)
        
        # events that do not have a group
        for event in Events.query.filter((Events.group_id == None)).all():
            if event.id not in event_ids:
                events.append({
                    'title': event.title,
                    'groupId': event.group_id,
                    'groupName': Groups.query.filter_by(id=event.group_id).first().name if Groups.query.filter_by(id=event.group_id).first() else None,
                    'start': f"{event.date.strftime('%Y-%m-%d')} {event.start_time}",
                    'end': f"{event.date.strftime('%Y-%m-%d')} {event.end_time}",
                    'modalId': event.id,
                    'description': event.description,
                    'n_assistants': event.n_assistants,
                    'backgroundColor': event.color if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else 'white',
                    'borderColor': event.color,
                    'textColor': 'black' if UserEvents.query.filter_by(event_id=event.id, user_id=user_id).first() else event.color
                })
                event_ids.add(event.id)

        return render_template("index.html", events=events, user_id=user_id)


@app.route('/export_participants_by_title', methods=['POST'])
@login_required
@permission_admin
def export_participants_by_title():
    '''
    Export function that generates an excel with all the participants of an event.
    '''
    # if no title is sent
    if not request.form.get('eventTitle'):
        flash("Must select a title.", "danger")
        return redirect("/")

    title = request.form.get('eventTitle')
    events_with_title = Events.query.filter_by(title=title).all()

    
    # Create a DataFrame with the participants' names for each event date and time
    participants_data = {}
    for event in events_with_title:
        event_date = event.date.strftime('%Y-%m-%d')
        event_time = f"{event.start_time} - {event.end_time}"
        if (event_date, event_time) not in participants_data:
            participants_data[(event_date, event_time)] = []
        event_participants = UserEvents.query.filter_by(event_id=event.id).join(Users).all()
        participants_data[(event_date, event_time)].extend([f"{participant.user.name} {participant.user.surname}" for participant in event_participants])
    
    # Manage the case where list of participants of each event do not have the same length
    max_length = max(len(participants) for participants in participants_data.values())
    for participants_list in participants_data.values():
        while len(participants_list) < max_length:
            participants_list.append('')
    
    # Create a DataFrame with the participants' names for each event date and time
    participants_df = pd.DataFrame(participants_data)

    # Create the Excel file in memory
    excel_file = io.BytesIO()
    participants_df.to_excel(excel_file)
    excel_file.seek(0)  # Move the cursor to the start of the file

    return send_file(excel_file, as_attachment=True, download_name=f'participants_{title}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export_participants/<int:event_id>')
@login_required
@permission_admin
def export_participants(event_id):
    # Logic to generate the Excel file
    # Replace this with your own logic to generate the Excel file
    # You can use libraries like pandas or openpyxl to create the Excel file
    
    # Assuming you have generated the Excel file and saved it as 'participants.xlsx'
    participants = UserEvents.query.filter_by(event_id=event_id).join(Users).all()
    
    # Create a DataFrame with the participants' names
    participants_df = pd.DataFrame([f"{participant.user.name} {participant.user.surname}" for participant in participants], columns=['Name'])

    # Create the Excel file in memory
    excel_file = io.BytesIO()
    participants_df.to_excel(excel_file)
    excel_file.seek(0)  # Move the cursor to the start of the file
    
    return send_file(excel_file, as_attachment=True, download_name=f'participants_event_{event_id}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    
@app.route("/create-event", methods=["GET", "POST"])
@login_required
@permission_admin
def create_event():
    """
    Form to create new event.
    """
    if request.method == "GET":

        groups = [(group.id, group.name) for group in Groups.query.all()]

        return render_template("create_event.html", groups=groups)
    else: #post
        
        # Get data from new event
        title = request.form.get("title")
        description = request.form.get("description") # if empty is ""
        group_id = request.form.get("group") # if empty is None
        n_assistants = request.form.get("n_assistants")
        color = request.form.get("color")

        for date, start_time, end_time in zip(request.form.getlist("dates[]"), request.form.getlist("start_times[]"), request.form.getlist("end_times[]")):
            date = datetime.strptime(date,'%Y-%m-%d').date()
            start_time = datetime.strptime(start_time, "%H:%M").time()
            end_time = datetime.strptime(end_time, "%H:%M").time()

            # Update DDBB
            new_event = Events(title=title, description=description, date=date, start_time=start_time, end_time=end_time, group_id=group_id, n_assistants=n_assistants, color=color)
            # Add the event to the database
            db_session.add(new_event)
            db_session.commit()

        return redirect("/")


@app.route("/add_user_event", methods=['POST'])
@login_required
def add_user_event():

    user_id = request.json.get('user_id')  
    event_id = request.json.get('event_id')
    
    # Verify if there is already a log with same user_id and event_id
    existing_log = UserEvents.query.filter_by(user_id=user_id, event_id=event_id).first()
    
    if existing_log:
        return jsonify({"message": "El log ya existe"})
    
    new_user_event = UserEvents(user_id=user_id, event_id=event_id)
    db_session.add(new_user_event)
    db_session.commit()
    
    return jsonify({"message": "Evento de usuario agregado exitosamente"})

@app.route('/delete_user_event', methods=['DELETE'])
@login_required
def delete_user_event():
    user_id = request.json.get('user_id')  
    event_id = request.json.get('event_id')
    
    # Buscar el log en la base de datos
    log_to_delete = UserEvents.query.filter_by(user_id=user_id, event_id=event_id).first()
    
    if log_to_delete:
        db_session.delete(log_to_delete)
        db_session.commit()
        return jsonify({"message": "Log eliminado exitosamente"})
    else:
        return jsonify({"message": "No se encontró el log"})


@app.route('/get_participants/<int:event_id>')
@login_required
def get_participants(event_id):
    participants = db_session.query(Users).join(UserEvents, Users.id == UserEvents.user_id).filter(UserEvents.event_id == event_id).all()

    return jsonify([{'id': participant.id, 'name': participant.name, 'surname': participant.surname} for participant in participants])


@app.route('/get_participation_status/<int:event_id>/<int:user_id>')
@login_required
def get_participation_status(event_id, user_id):
    user_event = UserEvents.query.filter_by(event_id=event_id, user_id=user_id).first()
    return jsonify({'participates': user_event is not None})


@app.route("/manage-groups", methods=["GET", "POST"])
@login_required
@permission_admin
def manage_groups():
    if request.method == "GET":
        all_users = [(user.id, user.name, user.surname, user.username) for user in Users.query.all()]

        groups = Groups.query.all()
        groups_with_users = []

        for group in groups:
            usergroups = UserGroups.query.filter_by(group_id=group.id).all()
            users = []
            
            for usergroup in usergroups:
                user = Users.query.filter_by(id=usergroup.user_id).first()
                users.append(user)
            groups_with_users.append({'group': group, 'users': users})
        return render_template("manage_groups.html", all_users=all_users, groups_with_users=groups_with_users)
    
    else: #post
        users_file = request.files["fileUpload"]
        
        existing_group = Groups.query.filter_by(name=request.form.get("name")).first()
        if existing_group:
            group_id = existing_group.id

            # Get the list of selected users
            selected_users = request.form.getlist('users[]')

            # Create UserGroup log for each user added
            for user_id in selected_users:
                user_group_log = UserGroups(user_id=user_id, group_id=group_id)
                db_session.add(user_group_log)
                db_session.commit()

            if users_file:
                excel_data = users_file.read()
                users_df = pd.read_excel(io.BytesIO(excel_data))
                
                for index, row in users_df.iterrows():
                    name = row['Nom']
                    surname = row['Primer cognom'] + ' ' + row['Segon cognom']
                    username = row['Correu']
                    hash = row['Nif']
                    role_id = 1

                    existing_user = Users.query.filter_by(username=username).first()
                    # Check that the user is new
                    if existing_user in None:
                        new_user = Users(name=name, surname=surname, username=username, hash=generate_password_hash(hash), role_id=role_id)
                        db_session.add(new_user)
                        db_session.commit()
                        user_group_log = UserGroups(user_id=new_user.id, group_id=group_id)
                        db_session.add(user_group_log)
                        db_session.commit()
                    
                    # Add the existing user to the group
                    else:
                        user_group_log = UserGroups(user_id=existing_user.id, group_id=group_id)
                        db_session.add(user_group_log)
                        db_session.commit()
        
        else:
            name = request.form.get("name")
            new_group = Groups(name=name)
            db_session.add(new_group)
            db_session.commit()

            group_id = new_group.id

            # Get the list of selected users
            selected_users = request.form.getlist('users[]')

            # Create UserGroup log for each user added
            for user_id in selected_users:
                user_group_log = UserGroups(user_id=user_id, group_id=group_id)
                db_session.add(user_group_log)
                db_session.commit()

            if users_file:
                excel_data = users_file.read()
                users_df = pd.read_excel(io.BytesIO(excel_data))

                for index, row in users_df.iterrows():
                    name = row['Nom']
                    surname = row['Primer cognom'] + ' ' + row['Segon cognom']
                    username = row['Correu']
                    hash = row['Nif']
                    role_id = 1

                    existing_user = Users.query.filter_by(username=username).first()
                    # Check that the user is new
                    if existing_user is None:
                        new_user = Users(name=name, surname=surname, username=username, hash=generate_password_hash(hash), role_id=role_id)
                        db_session.add(new_user)
                        db_session.commit()
                        user_group_log = UserGroups(user_id=new_user.id, group_id=group_id)
                        db_session.add(user_group_log)
                        db_session.commit()
                    
                    # Add the existing user to the group
                    else:
                        user_group_log = UserGroups(user_id=existing_user.id, group_id=group_id)
                        db_session.add(user_group_log)
                        db_session.commit()
        
        flash("Group created successfully!", "success")
        return redirect("/manage-groups")

@app.route('/add-user-group', methods=['POST'])
@login_required
@permission_admin
def add_user_group():
    
    group = Groups.query.filter_by(name=request.form.get("name")).first()
    group_id = group.id

    # Get the list of selected users
    selected_users = request.form.getlist('users[]')

    # Create UserGroup log for each user added
    for user_id in selected_users:
        user_group_log = UserGroups(user_id=user_id, group_id=group_id)
        db_session.add(user_group_log)
        db_session.commit()

        flash("User added to group.", "success")

    return redirect("/manage-groups")

@app.route('/delete_user_group', methods=['DELETE'])
@login_required
@permission_admin
def delete_user_group():
    user_id = request.json.get('user_id')  
    group_id = request.json.get('group_id')
    
    # Buscar el log en la base de datos
    log_to_delete = UserGroups.query.filter_by(user_id=user_id, group_id=group_id).first()
    
    if log_to_delete:
        db_session.delete(log_to_delete)
        db_session.commit()

        flash("User deleted from group.", "warning")

        return jsonify({"message": "Log eliminado exitosamente"})
    else:
        return jsonify({"message": "No se encontró el log"})

@app.route('/delete_group', methods=['DELETE'])
@login_required
@permission_admin
def delete_group():

    group_id = request.json.get('group_id')
    
    # Delete the logs in UserGroups table that contain the group_id
    UserGroups.query.filter_by(group_id=group_id).delete()
    
    # Buscar el log en la base de datos
    group_to_delete = Groups.query.filter_by(id=group_id).first()
    
    if group_to_delete:
        db_session.delete(group_to_delete)
        db_session.commit()

        flash("Group deleted.", "warning")

        return jsonify({"message": "Log eliminado exitosamente"})
    else:
        return jsonify({"message": "No se encontró el log"})

@app.route('/delete_event', methods=['DELETE'])
@login_required
@permission_admin
def delete_event():

    event_id = request.json.get('event_id')
    
    # Delete the logs in UserEvents table that contain the event_id
    UserEvents.query.filter_by(event_id=event_id).delete()
    
    # Buscar el log en la base de datos
    event_to_delete = Events.query.filter_by(id=event_id).first()
    
    if event_to_delete:
        db_session.delete(event_to_delete)
        db_session.commit()

        flash("Event deleted.", "warning")

        return jsonify({"message": "Log eliminado exitosamente"})
    else:
        return jsonify({"message": "No se encontró el log"})

@app.route("/assign-roles", methods=["GET", "POST"])
@login_required
@permission_admin
def assign_roles():
    if request.method == "GET":
        users = [(user.id, user.name, user.surname) for user in Users.query.all()]
        roles = [(role.id, role.role) for role in Roles.query.all()]

        return render_template("assign_roles.html", users=users, roles=roles)
    else:
        if not request.form.get("username"):
            flash("Must select a username.", "danger")
            return redirect("/assign-roles")
        elif not request.form.get("role"):
            flash("Must select a role.", "danger")
            return redirect("/assign-roles")
        
        user_id = request.form.get("username")
        role_id = request.form.get("role")

        # Find the user
        user = Users.query.filter_by(id=user_id).first()
        
        # Update the role_id
        user.role_id = role_id
        db_session.commit()

        flash("Role assigned successfully!", "success")

        return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    logout_user()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username
        user = Users.query.filter_by(username=request.form.get("username")).first()

        # Ensure username exists and password is correct
        if user == None or not check_password_hash(user.hash, request.form.get("password")):
            flash("Invalid username and/or password.", 'danger')
            return render_template("login.html")
        
        else: 
            login_user(user)

            flash("Successful login!", "success")

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    #session.clear()
    logout_user()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else: # method == 'POST'

        # Ensure confirm_password was submitted and is the same
        if request.form.get("confirmation") != request.form.get("password"):
            flash("Passwords must match.", "danger")
            return render_template("register.html")

        # Query database for name and surname
        existing_user = Users.query.filter_by(name=request.form.get("name"), surname=request.form.get("surname")).first()

        if existing_user is None: # Ensure name + surname do not exist
            # Query database for username
            rows = Users.query.filter_by(username=request.form.get("username")).first()
 
            if rows is None: # Ensure username does not exist
                # Create a new user (with role user by default)
                new_user = Users(name=request.form.get("name"), surname=request.form.get("surname"), username=request.form.get("username"), hash=generate_password_hash(request.form.get("password")), role_id=2)

                # Add the user to the database
                db_session.add(new_user)
                db_session.commit()
                flash("User registered successfully!", "success")

            else:
                flash("Username already exists.", "danger")
                return render_template("register.html")
        else:
            flash("Name and surname already exist.", "danger")
            return render_template("register.html")

        # Redirect user to home page
        return redirect("/")
    

@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Show form to change password"""
    if request.method == "GET":
        return render_template("password.html")

    else:

        # Ensure confirm_password is the same
        if request.form.get("confirmation") != request.form.get("password"):
            flash("Passwords must match.", "danger")
            return render_template("password.html")
        
        # Get the user you want to update
        user = Users.query.filter_by(id=current_user.id).first()

        # Update the user's hash
        user.hash = generate_password_hash(request.form.get("password"))

        # Commit the changes to the database
        db_session.commit()

        flash("Password changed successfully!", "success")

        # Redirect user to home page
        return redirect("/")