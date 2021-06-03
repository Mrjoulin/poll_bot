# Poll Bot
### Version 1.0

## Deploy

### Requirements:
 * #### GitHub (git)
 * #### Docker
 * #### docker-compose
### To run app:
```shell script
# Clone project
$ git clone https://github.com/Mrjoulin/poll_bot.git
$ cd poll_bot/         
# Run bot with docker-compose (prod)
$ sudo docker-copmose -f docker-compose.yaml up --build -d
# Run bot with docker-compose (stage, recommended for testing)
$ sudo docker-copmose -f docker-compose-dev.yaml up --build
```
