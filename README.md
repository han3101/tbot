# tbot
ICTbot is desinged to be a telegram bot created through telegram's grandfather bot

Tbot runs on any server (for our case we used a digital ocean's droplet VM) and will prompt users twice/thrice daily to update their temperature. Temperatures will be written and stored using pickleDB and retained for up to 14 days. 

High Temperature warnings will be triggered at custom high-temp settings and the bot will send the alert to the user with high temperature as well as designated users.
