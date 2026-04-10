#!/bin/bash
# Terminate all Locust swarm instances

set -e

echo "🛑 Terminating Locust Swarm..."
echo ""

# Check if instance IDs file exists
if [ -f /tmp/locust-swarm-instances.txt ]; then
  echo "📋 Loading instance IDs from /tmp/locust-swarm-instances.txt"
  source /tmp/locust-swarm-instances.txt

  ALL_INSTANCES="$MASTER_INSTANCE $WORKER_INSTANCES"

  echo "   Master: $MASTER_INSTANCE"
  echo "   Workers: $WORKER_INSTANCES"
  echo ""
  echo "Terminating instances..."

  aws ec2 terminate-instances --instance-ids $ALL_INSTANCES

  echo ""
  echo "✅ Termination initiated for all instances"

  # Clean up the file
  rm /tmp/locust-swarm-instances.txt

else
  echo "⚠️  No saved instance IDs found."
  echo "   Searching for all Locust instances by tag..."
  echo ""

  # Find all instances by Role tag
  INSTANCES=$(aws ec2 describe-instances \
    --filters "Name=tag:Role,Values=master,worker" "Name=instance-state-name,Values=running,pending,stopped" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text)

  if [ -z "$INSTANCES" ]; then
    echo "❌ No running Locust instances found."
    exit 0
  fi

  echo "Found instances: $INSTANCES"
  echo ""
  echo "Terminating..."

  aws ec2 terminate-instances --instance-ids $INSTANCES

  echo ""
  echo "✅ Termination initiated for all found instances"
fi

echo ""
echo "Verify termination with:"
echo "  aws ec2 describe-instances \\"
echo "    --filters \"Name=tag:Role,Values=master,worker\" \\"
echo "    --query 'Reservations[].Instances[].[InstanceId,State.Name]' \\"
echo "    --output table"
