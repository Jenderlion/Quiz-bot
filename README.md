# Welcome!
### What is this bot for?
As the name implies, the bot is a simple questionnaire, which is an addition to other methods of collecting information (for example, Google forms, etc.).

### What restrictions does it have?
1. Pause between messages - configurable (in code).
2. Only 10 polls are displayed (so as not to clutter up the user interface if [the editor](#what-user-groups-exist) is asleep).
3. You can not put several questions with [relationships](#how-to-add-a-poll) in a row.

### What user groups exist?
1. user - base group
2. editor [editor] - can add, hide, manage polls and get their results
3. admin - receives questions from users, manages groups and bans, conducts mailings
4. m_admin - the same as a regular admin, but cannot be banned or demoted.

### How does a bot work out of the box?
To get started, you need to use the bot to get an api-token (immediately after [installing all dependencies from requirements.txt](https://note.nkmk.me/en/python-pip-install-requirements/)). The first time you run the console, you will be asked to enter this token, as well as all the parameters for connecting to the database. Success! The bot is running and you can proceed to adding the first survey. By the way, you did not forget to set yourself the status m_admin? You have to do it manually :(

### How to add a poll?
To do this, you need to prepare a text file with the following structure:

|Service quality                                                        <- quiz name

|A little poll to let us know if you liked everything!                  <- quiz title

|1. What time did you visit us?//\\Morning/\Afternoon/\Evening          <- regular question

|[{1 -> Evening}]2. Before or after rush hour?//\\Before/\After         <- question relation

|3. Please leave a short review about our establishment//\\MANUAL_INPUT <- manual input

|Thank you for taking a moment :)                                       <- thanksgiving line

|                                                                       <- yes, it's a blank line

The finished file just needs to be sent to the bot (the name must be unique, if something goes wrong - you will be informed) to any user with editor or administrator rights. If successful, the bot will inform you.

Once added, all polls are hidden - just in case the addition happened by accident or an error was found. To change the display status, use the /quiz vis id True/False command. Oh sure, if you forgot something, you can always type /quiz, /editor, /ban, /unban, /message and /role to the bot to get a hint (assuming you have permissions, of course)

The answer to most questions will be given by the bot itself. By the way, it is distributed only for non-commercial use. If you have any questions, you can always contact me on github or by e-mail.
