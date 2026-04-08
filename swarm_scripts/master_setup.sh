#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y python3 python3-pip git

# Create locust user
useradd -m -s /bin/bash locust

# Clone repository
cd /home/locust
git clone https://github.com/kidspassport/sawyer-load-test.git
cd sawyer-load-test

# Remove problematic system packages that conflict with pip
apt-get remove -y python3-blinker python3-zope.interface python3-urllib3 python3-requests || true

# Install Python dependencies - upgrade pip first
pip3 install --upgrade pip setuptools wheel

# Force install gevent and its dependencies first
pip3 install --force-reinstall --no-cache-dir zope.event zope.interface greenlet gevent

# Force reinstall urllib3 and requests to ensure correct versions
pip3 install --force-reinstall --no-cache-dir urllib3 requests

# Now install other requirements
pip3 install -r requirements.txt

# Create systemd service for master
cat > /etc/systemd/system/locust-master.service <<EOF
[Unit]
Description=Locust Master
After=network.target

[Service]
Type=simple
User=locust
WorkingDirectory=/home/locust/sawyer-load-test
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/local/bin/locust \
  --master \
  --master-bind-port=5557 \
  --web-port=8089 \
  --expect-workers=3 \
  --scenario=place_order \
  --slug=pretend-school \
  --booking_fee_id=306 \
  --host=https://staging.hisawyer.com
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Set ownership
chown -R locust:locust /home/locust/sawyer-load-test

# Enable and start service
systemctl daemon-reload
systemctl enable locust-master
systemctl start locust-master

# Install CloudWatch agent for monitoring (optional but recommended)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
dpkg -i amazon-cloudwatch-agent.deb
