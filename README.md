# My Kiosk Bot
### Version 1.1
### URL: https://mykiosk.cc/

## Deploy

### Requirements:
 * #### GitHub (git)
 * #### Docker
 * #### docker-compose
### To run app:
```shell script
# Clone project
$ git clone https://github.com/my-kiosk-team/KioskBot
$ cd KioskBot/                
# Run bot with docker-compose (prod)
$ sudo docker-copmose -f docker-compose.yaml up --build -d
# Run bot with docker-compose (stage, recommended for testing)
$ sudo docker-copmose -f docker-compose-dev.yaml up --build
```

## Documentation
### - [API Documentation](https://github.com/my-kiosk-team/KioskBot/tree/master/api)
### - [Database structure](https://github.com/my-kiosk-team/KioskBot/tree/master/api/api)
