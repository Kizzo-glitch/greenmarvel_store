from django.db import models

class Promotion(models.Model):
	name = models.CharField(max_length=100)
	start_date = models.DateTimeField()
	end_date = models.DateTimeField()
	is_active = models.BooleanField(default=False)

	def is_running(self):
		from django.utils import timezone
		now = timezone.now()
		return self.is_active and self.start_date <= now <= self.end_date
