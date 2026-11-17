# Email Appointment Checker and Accepter Script
This automation script uses environmental variables to login an email account and check for emails based on a certain address. The scripts run between 9am and 6pm daily on workdays. The interact with UI script looks for UI elements with accept and selects them using Selenium.

Setup envirnmental variables before running.
setx APPT_EMAIL "email address"
setx APPT_APP_PASSWORD "email password"

Change to expected email address
SENDER_FILTER = "Expected_Email_Address@.com"
