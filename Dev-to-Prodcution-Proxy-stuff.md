
Generis config to set before certbot just enough to get the cert

# /etc/nginx/sites-available/voice.aetherpro.us
server {
    listen 80;
    server_name voice.aetherpro.us;

    # API + WS (Twilio ws endpoint is under /api/v1/ws/...)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600;
    }

    # FastAPI docs endpoints
    location = /docs { proxy_pass http://127.0.0.1:8000; }
    location = /redoc { proxy_pass http://127.0.0.1:8000; }
    location = /openapi.json { proxy_pass http://127.0.0.1:8000; }

    # Optional metrics
    location = /metrics { proxy_pass http://127.0.0.1:8000; }

    # UI
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}


Production config after certbot does it's thing.

# /etc/nginx/sites-available/voice.aetherpro.us
server {
    listen 80;
    server_name voice.aetherpro.us;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name voice.aetherpro.us;

    ssl_certificate     /etc/nginx/ssl/voice.aetherpro.us/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/voice.aetherpro.us/privkey.pem;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600;
    }

    location = /docs { proxy_pass http://127.0.0.1:8000; }
    location = /redoc { proxy_pass http://127.0.0.1:8000; }
    location = /openapi.json { proxy_pass http://127.0.0.1:8000; }
    location = /metrics { proxy_pass http://127.0.0.1:8000; }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

