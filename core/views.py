from django.contrib.auth.forms import UserCreationForm

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from .forms import AppointmentForm, WellnessTaskForm
from .models import AssessmentQuestion, Appointment, Counselor, PeerSupport, WellnessTask, TemplateWellnessTask, AppointmentSlot, PeerChatSession, PeerChatMessage

from django.contrib.auth.models import User
from datetime import datetime, date
from .gemini_utils import get_gemini_response
from .twilio_utils import send_whatsapp_message
from .zoom_utils import create_zoom_meeting

def is_admin(user):
    return user.is_superuser

from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    return render(request, 'core/home.html')


@login_required
def chatbot(request):
    ai_response = None
    if request.method == 'POST':
        user_message = request.POST.get('user_message')
        if user_message:
            ai_response = get_gemini_response(user_message, role='assistant')
    return render(request, 'core/chatbot.html', {'ai_response': ai_response})


# New: Step-by-step assessment, one question at a time

@login_required
def assessment(request):
    # Get all questions (PHQ-9 + GAD-7) in order
    questions = list(AssessmentQuestion.objects.order_by('category', 'id'))
    total_questions = len(questions)
    # Use session to track progress
    if 'assessment_answers' not in request.session:
        request.session['assessment_answers'] = []
        request.session['assessment_index'] = 0
        request.session['assessment_intro'] = True

    answers = request.session['assessment_answers']
    index = request.session['assessment_index']
    show_intro = request.session.get('assessment_intro', True)

    if request.method == 'POST':
        if show_intro:
            # User pressed start after seeing intro
            request.session['assessment_intro'] = False
            show_intro = False
        else:
            answer = request.POST.get('answer')
            if answer is not None and answer.isdigit():
                answers.append(int(answer))
                index += 1
                request.session['assessment_answers'] = answers
                request.session['assessment_index'] = index

    if not show_intro and index >= total_questions:
        # Show the last question with view results button
        question = questions[-1] if questions else None
        index = total_questions - 1

    if request.method == 'POST' and 'view_results' in request.POST:
        # All questions answered, analyze
        phq9_score = sum(answers[:9]) if len(answers) >= 9 else 0
        gad7_score = sum(answers[9:16]) if len(answers) >= 16 else 0
        # Store scores in session for result page
        request.session['phq9_score'] = phq9_score
        request.session['gad7_score'] = gad7_score
        # Clear session
        del request.session['assessment_answers']
        del request.session['assessment_index']
        del request.session['assessment_intro']
        return redirect('assessment_result')

    ai_chat_response = None

    # Always show intro before first question
    if show_intro or (index == 0 and request.method != 'POST'):
        request.session['assessment_intro'] = True
        if request.method == 'POST':
            # User pressed start after seeing intro
            request.session['assessment_intro'] = False
            return redirect('assessment')
        return render(request, 'core/assessment_intro.html')

    question = questions[index] if index < total_questions else None

    if request.method == 'POST':
        user_message = request.POST.get('ai_chat_message')
        if user_message:
            # If the user types a number (0-3), treat as answer
            if user_message.strip() in ['0', '1', '2', '3']:
                answers.append(int(user_message.strip()))
                index += 1
                request.session['assessment_answers'] = answers
                request.session['assessment_index'] = index
                # Move to next question
                if index < total_questions:
                    question = questions[index]
                else:
                    question = None
            else:
                # Otherwise, treat as AI chat
                prompt = f"A student is taking a mental health assessment. The current question is: '{question.text}'. The student asks: '{user_message}'. Please answer as a supportive mental health assistant."
                ai_chat_response = get_gemini_response(prompt, role='mental health assistant')

    return render(request, 'core/assessment_step.html', {
        'question': question,
        'index': index+1,
        'total': total_questions,
        'ai_chat_response': ai_chat_response
    })

@login_required
def assessment_result(request):
    phq9_score = request.session.get('phq9_score')
    gad7_score = request.session.get('gad7_score')

    if phq9_score is None or gad7_score is None:
        # If no scores in session, redirect to assessment start
        return redirect('assessment')

    # Determine risk level based on scores (example thresholds)
    if phq9_score < 5 and gad7_score < 5:
        risk_level = 'low'
    elif phq9_score < 15 and gad7_score < 15:
        risk_level = 'medium'
    else:
        risk_level = 'high'

    # Clear scores from session after use
    del request.session['phq9_score']
    del request.session['gad7_score']

    # For low risk, show recommendations button
    # For medium risk, show peer support button
    # For high risk, show counselor selection and booking

    counselors = None
    if risk_level == 'high':
        counselors = Counselor.objects.all()

    return render(request, 'core/assessment_result.html', {
        'phq9_score': phq9_score,
        'gad7_score': gad7_score,
        'risk_level': risk_level,
        'counselors': counselors
    })

@login_required
def recommendations(request):
    # Show relaxation tips, meditation videos, mental exercises
    return render(request, 'core/recommendations.html')

@login_required
def peer_support(request):
    user = request.user

    # Check if user already has an active chat session
    existing_session = PeerChatSession.objects.filter(
        (Q(user1=user) | Q(user2=user)) & Q(active=True)
    ).first()

    if existing_session:
        session = existing_session
    else:
        # Try to find another user without an active session
        other_users = User.objects.exclude(id=user.id).exclude(is_superuser=True)
        available_user = None
        for u in other_users:
            if not PeerChatSession.objects.filter(
                (Q(user1=u) | Q(user2=u)) & Q(active=True)
            ).exists():
                available_user = u
                break

        if available_user:
            # Create a new session with the available user
            session = PeerChatSession.objects.create(user1=user, user2=available_user)
        else:
            # No available user, create a session for later pairing
            # For now, create a dummy session or show waiting
            # To make it work, I'll create a session with the user as both, but that's not ideal
            # For demo, I'll pair with the first other user if exists
            if other_users.exists():
                session = PeerChatSession.objects.create(user1=user, user2=other_users.first())
            else:
                # No other users, show waiting
                return render(request, 'core/peer_support.html', {'waiting': True})

    # Handle message sending
    if request.method == 'POST' and 'message' in request.POST:
        message_text = request.POST.get('message').strip()
        if message_text:
            PeerChatMessage.objects.create(session=session, sender=user, message=message_text)
            # Redirect to avoid duplicate form submission on refresh
            return redirect('peer_support')

    # Get all messages for the session
    messages = PeerChatMessage.objects.filter(session=session).order_by('timestamp')

    # Determine the peer
    peer = session.user2 if session.user1 == user else session.user1

    return render(request, 'core/peer_support.html', {
        'session': session,
        'messages': messages,
        'peer': peer,
        'waiting': False
    })

@login_required
def future_you(request):
    # Initialize conversation history in session if not present
    if 'future_you_conversation' not in request.session:
        request.session['future_you_conversation'] = []

    conversation = request.session['future_you_conversation']

    if request.method == 'POST':
        user_message = request.POST.get('user_message')
        if user_message:
            # Add user message to conversation
            conversation.append({'role': 'user', 'message': user_message})
            # Build prompt with conversation history
            prompt = "You are the user, but 10 years older. Motivate and respond as their future self. Conversation history:\n"
            for msg in conversation:
                if msg['role'] == 'user':
                    prompt += f"User: {msg['message']}\n"
                else:
                    prompt += f"Future Self: {msg['message']}\n"
            prompt += "Future Self:"
            ai_response = get_gemini_response(prompt, role='future self')
            # Add AI response to conversation
            conversation.append({'role': 'ai', 'message': ai_response})
            request.session['future_you_conversation'] = conversation

    return render(request, 'core/future_you.html', {'conversation': conversation})

@login_required
def appointment_list(request):
    appointments = Appointment.objects.filter(user=request.user)
    return render(request, 'core/appointment_list.html', {'appointments': appointments})


@login_required
def book_appointment(request):
    user = request.user
    slot_id = request.POST.get('slot_id')

    if request.method == 'POST' and slot_id:
        # User selected a slot to book
        try:
            slot = AppointmentSlot.objects.get(id=slot_id, is_booked=False)
            # Mark slot as booked
            slot.is_booked = True
            slot.save()
            # Create Appointment
            appointment = Appointment.objects.create(
                user=user,
                counselor=slot.counselor,
                date=slot.slot_time,
                status='Confirmed'
            )
            # Send WhatsApp to counselor
            counselor = slot.counselor
            message = f"You have a new booking with {user.username} on {slot.slot_time.strftime('%Y-%m-%d %H:%M')}."
            send_whatsapp_message(counselor.contact, message)
            # Create Zoom meeting
            zoom_url, zoom_err = create_zoom_meeting(
                topic=f"Counseling Session: {user.username}",
                start_time=slot.slot_time,
                duration=30
            )
            # Optionally, send Zoom link to both counselor and user (WhatsApp/email)
            if zoom_url:
                send_whatsapp_message(counselor.contact, f"Zoom meeting link: {zoom_url}")
                if hasattr(user, 'profile') and getattr(user.profile, 'phone', None):
                    send_whatsapp_message(user.profile.phone, f"Your counseling session Zoom link: {zoom_url}")
            return redirect('appointment_list')
        except AppointmentSlot.DoesNotExist:
            return render(request, 'core/book_appointment.html', {'slots': [], 'error': 'Selected slot is no longer available.'})

    # Get all available slots ordered by time
    slots = AppointmentSlot.objects.filter(is_booked=False).order_by('slot_time')
    if not slots:
        return render(request, 'core/book_appointment.html', {'slots': [], 'error': 'No available slots at this time.'})

    return render(request, 'core/book_appointment.html', {'slots': slots})

@login_required
def profile(request):
    tasks = WellnessTask.objects.filter(assigned_to=request.user)
    today = date.today()
    return render(request, 'core/profile.html', {'tasks': tasks, 'today': today})

@login_required
def wellness_activity(request):
    user = request.user
    today = date.today()
    # Count how many tasks have already been assigned to this user
    assigned_count = WellnessTask.objects.filter(assigned_to=user).count()
    # Get the next template task (if any)
    next_template = TemplateWellnessTask.objects.order_by('order')[assigned_count:assigned_count+1].first()
    if next_template:
        # Check if today's task is already assigned
        already_assigned = WellnessTask.objects.filter(assigned_to=user, date=today, task=next_template.task).exists()
        if not already_assigned:
            WellnessTask.objects.create(
                task=next_template.task,
                assigned_by=None,
                assigned_to=user,
                date=today,
                completed=False
            )
    # Only show today's task
    todays_task = WellnessTask.objects.filter(assigned_to=user, date=today).first()
    return render(request, 'core/wellness_activity.html', {'todays_task': todays_task})

@login_required
def mark_task_completed(request, task_id):
    task = WellnessTask.objects.get(id=task_id, assigned_to=request.user)
    task.completed = True
    task.save()
    return redirect('wellness_activity')

@user_passes_test(is_admin)
def admin_panel(request):
    return render(request, 'core/admin_panel.html')

@user_passes_test(is_admin)
def add_counselor(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        hospital = request.POST.get('hospital')
        contact = request.POST.get('contact')
        Counselor.objects.create(name=name, location=location, hospital=hospital, contact=contact)
        return redirect('admin_panel')
    return render(request, 'core/add_counselor.html')

@user_passes_test(is_admin)
def add_question(request):
    if request.method == 'POST':
        text = request.POST.get('text')
        category = request.POST.get('category')
        AssessmentQuestion.objects.create(text=text, category=category)
        return redirect('admin_panel')
    return render(request, 'core/add_question.html')

@user_passes_test(is_admin)
def add_task(request):
    if request.method == 'POST':
        task = request.POST.get('task')
        assigned_to_id = request.POST.get('assigned_to')
        date_str = request.POST.get('date')
        assigned_to = User.objects.get(id=assigned_to_id)
        WellnessTask.objects.create(task=task, assigned_to=assigned_to, date=date_str)
        return redirect('admin_panel')
    users = User.objects.filter(is_superuser=False)
    return render(request, 'core/add_task.html', {'users': users})
