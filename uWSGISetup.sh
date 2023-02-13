#!/bin/bash

if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

projectName = "yookassaproxy"

read -p "Enter domain name for your proxy (like this: my.proxydomain.com): " domainName
read -p "Enter email for certbot notifications: " certbotMail
read -p "Enter yookassa account ID: " yookassaAccountID
read -p "Enter yookassa secret key: " yookassaSecretKey
read -p "Enter connection token: " connectionToken
read -p "Do you have reverse-proxy? y/n: " hasReverseProxy

echo "installing binaries for unzipping, python and uWSGI..."
apt -yq update
apt -yq install wget build-essential python3-dev python3-pip install uwsgi flask

echo "downloading project from git..."
cd /root
wget 'https://github.com/kirovreporting/$projectName/archive/refs/heads/master.zip'
unzip master.zip
mv ${projectName}-master ${projectName}
cd ${projectName}

################# UWSGI.INI #################

if [[ ${hasReverseProxy} == "y" ]]

echo "creating uWSGI config file..."
cat << EOF > uwsgi.ini
[uwsgi]
module = wsgi:app

master = true
processes = 5
wsgi-file = /root/${projectName}/${projectName}.py
http-socket = 127.0.0.1:3030
stats = 127.0.0.1:3131
vacuum = true

die-on-term = true
EOF

elif

echo "creating uWSGI config file..."
cat << EOF > uwsgi.ini
[uwsgi]
module = wsgi:app

master = true
processes = 5
wsgi-file = /root/${projectName}/${projectName}.py
socket = /tmp/${projectName}.sock
chmod-socket = 660
vacuum = true

die-on-term = true
EOF

fi

#############################################

echo "creating app config file..."
cat << EOF > config.json
{
    "yookassaAccountID": "${yookassaAccountID}",
    "yookassaSecretKey": "${yookassaSecretKey}",
    "connectionToken": "${connectionToken}"
    "database": "db.sqlite",
    "debug": false
}
EOF

echo "registering and starting uWSGI service..."
cat << EOF > /etc/systemd/system/uwsgi.service
[Unit]
Description=uWSGI instance
After=network.target

[Service]
Group=www-data
WorkingDirectory=/root/${projectName}/
ExecStart=/usr/local/bin/uwsgi --ini /root/${projectName}/uwsgi.ini
Restart=always
KillSignal=SIGQUIT
Type=notify
NotifyAccess=all

[Install]
WantedBy=multi-user.target
EOF
systemctl start uwsgi
systemctl enable uwsgi

#################  NGINX INSTALL #################

if [[ ${hasReverseProxy} == "y" ]]

echo "installing nginx..."
apt -yq install nginx

echo "creating nginx config..."
cat << EOF > /etc/nginx/sites-available/${projectName}
server {
    listen 80;
    server_name ${domainname};

    location / {
        include uwsgi_params;
        uwsgi_pass unix:/root/${projectName}/${projectName}.sock;
    }
}
EOF
unlink /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/${projectName} /etc/nginx/sites-enabled

echo "starting nginx..."
systemctl restart nginx

echo "installing certbot..."
apt -yq install certbot python3-certbot-nginx

echo "issuing certs..."
certbot --nginx -d $domainName --non-interactive --agree-tos -m $certbotMail

fi

##################################################

echo "done. bye!"
exit 0