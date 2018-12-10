FROM ubuntu:latest
  
MAINTAINER John Samuel <johnsamuelwrites@gmail.com>

RUN apt -y update && \
    apt -y upgrade && \
    apt -y install apache2 git

RUN git clone https://github.com/johnsamuelwrites/johnsamuelwrites.github.io 

RUN rm -rf /var/www/html

RUN mv johnsamuelwrites.github.io /var/www/html

RUN echo "ServerName localhost" >>/etc/apache2/apache2.conf

EXPOSE 80

CMD apachectl -D FOREGROUND
