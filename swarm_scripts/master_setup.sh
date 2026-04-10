#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y python3 python3-pip python3-venv git

# Create locust user
useradd -m -s /bin/bash locust

# Clone repository
cd /home/locust
git clone https://github.com/kidspassport/sawyer-load-test.git
cd sawyer-load-test

# Create virtual environment
python3 -m venv /home/locust/venv

# Install Python dependencies in virtual environment
/home/locust/venv/bin/pip install --upgrade pip setuptools wheel
/home/locust/venv/bin/pip install -r requirements.txt

# Create systemd service for master
cat > /etc/systemd/system/locust-master.service <<EOF
[Unit]
Description=Locust Master
After=network.target

[Service]
Type=simple
User=locust
WorkingDirectory=/home/locust/sawyer-load-test
Environment="PATH=/home/locust/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="LOAD_TEST_TOKEN=\${load_test_token}"
ExecStart=/home/locust/venv/bin/locust \\
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
