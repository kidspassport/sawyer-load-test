#!/bin/bash
# Launch a Locust swarm on EC2 (1 master + 3 workers)

set -e

echo "🚀 Launching Locust Swarm on EC2..."
echo ""

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | grep -v '^#' | xargs)
  echo "✓ Loaded environment variables from .env"
else
  echo "⚠️  No .env file found. Create one from .env.example"
  echo "   Copy .env.example to .env and set LOAD_TEST_TOKEN"
  exit 1
fi

# Validate that LOAD_TEST_TOKEN is set
if [ -z "$LOAD_TEST_TOKEN" ]; then
  echo "❌ LOAD_TEST_TOKEN not set in .env file"
  echo "   Generate a token with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
  exit 1
fi

echo "✓ Load test token configured"
echo ""

# Configuration
WORKER_COUNT=3
INSTANCE_TYPE="t3.medium"
KEY_NAME="locust-key"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
  echo "❌ AWS CLI is not installed"
  echo "   Install it with: brew install awscli (macOS) or pip install awscli"
  echo "   See: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
  echo "❌ AWS credentials not configured"
  echo "   Run: aws configure"
  echo "   You'll need your AWS Access Key ID and Secret Access Key"
  exit 1
fi

echo "✓ AWS CLI configured"
echo ""

# Get latest Ubuntu 22.04 AMI
echo "📦 Finding latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)
echo "   Using AMI: $AMI_ID"

# Get security group IDs
echo ""
echo "🔒 Getting security groups..."
MASTER_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=locust-master-sg" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)
echo "   Master SG: $MASTER_SG"

WORKER_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=locust-worker-sg" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)
echo "   Worker SG: $WORKER_SG"

# Create master user-data with load test token
echo ""
echo "📝 Creating master configuration with load test token..."
sed "s/\${load_test_token}/$LOAD_TEST_TOKEN/g" swarm_scripts/master_setup.sh > /tmp/master-user-data.sh

# Launch master instance
echo ""
echo "🎯 Launching master instance..."
MASTER_INSTANCE=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $MASTER_SG \
  --user-data file:///tmp/master-user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=locust-master},{Key=Role,Value=master}]' \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "   Master instance: $MASTER_INSTANCE"

# Wait for master to be running
echo "   Waiting for master to be running..."
aws ec2 wait instance-running --instance-ids $MASTER_INSTANCE

# Get master IPs
MASTER_PRIVATE_IP=$(aws ec2 describe-instances \
  --instance-ids $MASTER_INSTANCE \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' \
  --output text)

MASTER_PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $MASTER_INSTANCE \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "   Master Private IP: $MASTER_PRIVATE_IP"
echo "   Master Public IP: $MASTER_PUBLIC_IP"

# Create worker user-data with master IP and load test token
echo ""
echo "📝 Creating worker configuration..."
sed "s/\${master_ip}/$MASTER_PRIVATE_IP/g" swarm_scripts/worker_setup.sh | sed "s/\${load_test_token}/$LOAD_TEST_TOKEN/g" > /tmp/worker-user-data.sh

# Launch worker instances
echo ""
echo "👷 Launching $WORKER_COUNT worker instances..."
WORKER_INSTANCES=()
for i in $(seq 1 $WORKER_COUNT); do
  WORKER_INSTANCE=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $WORKER_SG \
    --user-data file:///tmp/worker-user-data.sh \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=locust-worker-$i},{Key=Role,Value=worker}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

  WORKER_INSTANCES+=($WORKER_INSTANCE)
  echo "   Worker $i: $WORKER_INSTANCE"
done

# Save instance IDs for later
echo ""
echo "💾 Saving instance IDs..."
cat > /tmp/locust-swarm-instances.txt <<EOF
MASTER_INSTANCE=$MASTER_INSTANCE
MASTER_PUBLIC_IP=$MASTER_PUBLIC_IP
MASTER_PRIVATE_IP=$MASTER_PRIVATE_IP
WORKER_INSTANCES="${WORKER_INSTANCES[@]}"
EOF

echo "   Saved to /tmp/locust-swarm-instances.txt"

# Summary
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Swarm Launch Complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Master Instance:  $MASTER_INSTANCE"
echo "Worker Instances: ${WORKER_INSTANCES[@]}"
echo ""
echo "🌐 Web UI will be available at (wait 3-5 min for setup):"
echo "   http://$MASTER_PUBLIC_IP:8089"
echo ""
echo "📊 To check setup progress:"
echo "   ssh -i ~/.ssh/$KEY_NAME.pem ubuntu@$MASTER_PUBLIC_IP"
echo "   sudo journalctl -u locust-master -f"
echo ""
echo "🛑 To terminate all instances:"
echo "   ./terminate-swarm.sh"
echo ""
echo "⏰ Setup takes 3-5 minutes. Workers will auto-connect to master."
echo "════════════════════════════════════════════════════════════"
