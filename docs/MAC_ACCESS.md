# Mac browser access to OmniGuard on AWS EC2

Streamlit and the API bind to `127.0.0.1` on purpose. Do **not** open port 8501
with a public security-group rule for the hackathon demo.

## Preferred: AWS Systems Manager port forwarding

On your Mac (not on EC2):

```bash
aws --version
session-manager-plugin --version
aws sts get-caller-identity

aws ssm start-session \
  --target i-INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8501"],"localPortNumber":["8501"]}' \
  --region YOUR_REGION
```

Keep that terminal open, then browse:

```text
http://127.0.0.1:8501
```

Streamlit calls the API server-side on the instance, so forwarding **8501 alone**
is enough for the current dashboard.

## Session Manager plugin (macOS)

Install guide:
https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-macos-overview.html

## Observing Isaac visually

The twin GUI still runs on the EC2 DCV desktop. Use DCV for robot motion visuals;
use the Mac browser for OmniGuard controls and evidence.

## If SSM is unavailable

Resolve IAM / Session Manager access with the organizer before choosing any
public exposure workaround.
