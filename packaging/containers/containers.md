# Installation using Containers

## Docker 

Refer [Dockerfile](./Dockerfile)

### Building the image
In order to build the Docker image, run the following command

`docker build -t johnsamuel .`

### Running the image
Once successfully built, run the following command

`sudo docker run -dit -p 8080:80 johnsamuel`

### Browser

Open [http://localhost:8080/](http://localhost:8080/).


### Rebuilding the image
In order to build the Docker image, run the following command

`docker build --no-cache -t johnsamuel .`
