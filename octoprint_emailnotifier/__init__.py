# coding=utf-8
from __future__ import absolute_import
import os
import octoprint.plugin
import yagmail
import flask

class EmailNotifierPlugin(octoprint.plugin.EventHandlerPlugin,
                          octoprint.plugin.SettingsPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.AssetPlugin,
						  octoprint.plugin.SimpleApiPlugin):
	
	#~~ AssetPlugin

	def get_assets(self):
		return dict(
			js=["js/emailnotifier.js"]
		)

	#~~ SettingsPlugin

	def get_settings_defaults(self):
		# matching password must be registered in system keyring
		# to support customizable mail server, may need port too
		return dict(
			enabled=False,
			recipient_address="",
			mail_server="",
			mail_username="",
			mail_useralias="",
			include_snapshot=True,
			message_format=dict(
				title="Print job complete",
				body="{filename} done printing after {elapsed_time}" 
			)
		)
	
	def get_settings_version(self):
		return 1

	#~~ TemplatePlugin

	def get_template_configs(self):
		return [
			dict(type="settings", name="Email Notifier", custom_bindings=True)
		]

	#~~ EventPlugin

	def on_event(self, event, payload):
		if event != "PrintDone":
			return
		
		if not self._settings.get(['enabled']):
			return
		
		filename = os.path.basename(payload["file"])
		
		import datetime
		import octoprint.util
		elapsed_time = octoprint.util.get_formatted_timedelta(datetime.timedelta(seconds=payload["time"]))
		
		tags = {'filename': filename, 'elapsed_time': elapsed_time}
		title = self._settings.get(["message_format", "title"]).format(**tags)
		message = self._settings.get(["message_format", "body"]).format(**tags)
		content = [message]
		
		if self._settings.get(['include_snapshot']):
			snapshot_url = self._settings.globalGet(["webcam", "snapshot"])
			if snapshot_url:
				try:
					import urllib
					filename, headers = urllib.urlretrieve(snapshot_url)
				except Exception as e:
					self._logger.exception("Snapshot error (sending email notification without image): %s" % (str(e)))
				else:
					content.append({filename: "snapshot.jpg"})
		
		try:
			mailer = yagmail.SMTP(user={self._settings.get(['mail_username']):self._settings.get(['mail_useralias'])}, host=self._settings.get(['mail_server']))
			emails = [email.strip() for email in self._settings.get(['recipient_address']).split(',')]
			mailer.send(to=emails, subject=title, contents=content, validate_email=False)
		except Exception as e:
			# report problem sending email
			self._logger.exception("Email notification error: %s" % (str(e)))
		else:
			# report notification was sent
			self._logger.info("Print notification emailed to %s" % (self._settings.get(['recipient_address'])))		

	def get_update_information(self):
		return dict(
			emailnotifier=dict(
				displayName="EmailNotifier Plugin",
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="anoved",
				repo="OctoPrint-EmailNotifier",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/anoved/OctoPrint-EmailNotifier/archive/{target_version}.zip",
				dependency_links=False
			)
		)

	#~~ SimpleApiPlugin

	def get_api_commands(self):
		return dict(
			testmail=[]
		)

	def on_api_command(self, command, data):
		if command == "testmail":
			succeeded = True

			title = "OctoPrint Email Notifier Test"
			content = ["Test notification email"]

			if data["snapshot"]:
				snapshot_url = self._settings.globalGet(["webcam", "snapshot"])
				if snapshot_url:
					try:
						import urllib
						filename, headers = urllib.urlretrieve(snapshot_url)
					except Exception as e:
						self._logger.exception("Snapshot error (sending email notification without image): %s" % (str(e)))
						succeeded = False
					else:
						content.append({filename: "snapshot.jpg"})

			try:
				mailer = yagmail.SMTP(user={data["user"]:data["alias"]}, host=data["smtp"])

				# yagmail doesn't seem to like non str objects
				emails = [str(email.strip()) for email in data['recipients'].split(',')]

				mailer.send(to=emails, subject=title, contents=content, validate_email=False)
			except Exception as e:
				# report problem sending email
				self._logger.exception("Email notification error: %s" % (str(e)))
				succeeded = False
				return flask.jsonify(success=succeeded, msg=str(e))

			return flask.jsonify(success=succeeded)

		# else: unknown command response
		return flask.make_response("Unknown command", 400)


__plugin_name__ = "Email Notifier"

def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = EmailNotifierPlugin()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
