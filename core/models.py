
from django.db import models
from django.contrib.auth.models import User

# Admin sets available slots for each counselor
class AppointmentSlot(models.Model):
    counselor = models.ForeignKey('Counselor', on_delete=models.CASCADE)
    slot_time = models.DateTimeField()
    is_booked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.counselor.name} - {self.slot_time} ({'Booked' if self.is_booked else 'Available'})"

# Template for daily wellness tasks (admin enters 30 tasks here)
class TemplateWellnessTask(models.Model):
    task = models.CharField(max_length=255)
    order = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.order}: {self.task}"

class Counselor(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    hospital = models.CharField(max_length=100)
    contact = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class AssessmentQuestion(models.Model):
    CATEGORY_CHOICES = [
        ('PHQ9', 'PHQ-9'),
        ('GAD7', 'GAD-7'),
    ]
    text = models.CharField(max_length=255)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    def __str__(self):
        return f"{self.category}: {self.text}"

class Appointment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    counselor = models.ForeignKey(Counselor, on_delete=models.CASCADE)
    date = models.DateTimeField()
    status = models.CharField(max_length=20, default='Pending')

class PeerSupport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='peer_user')
    peer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='peer_peer')
    issue = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

class PeerChatSession(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"Chat between {self.user1.username} and {self.user2.username}"

class PeerChatMessage(models.Model):
    session = models.ForeignKey(PeerChatSession, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.message[:50]}"

class WellnessTask(models.Model):
    task = models.CharField(max_length=255)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wellness_tasks')
    date = models.DateField()
    completed = models.BooleanField(default=False)

    def __str__(self):
        return self.task
