# Stripe webhook path only → API :8002; all other traffic → Next :3000.
# Canonical webhook URL: https://app.hyerpath.com/api/billing/webhooks/stripe

hyerpath.com, www.hyerpath.com {
	handle /api/billing/webhooks/stripe* {
		reverse_proxy 127.0.0.1:8002
	}
	handle {
		reverse_proxy 127.0.0.1:3000 {
			header_up Host {host}
		}
	}
}

app.hyerpath.com {
	handle /api/billing/webhooks/stripe* {
		reverse_proxy 127.0.0.1:8002
	}
	handle {
		reverse_proxy 127.0.0.1:3000 {
			header_up Host {host}
		}
	}
}

osint.hyerpath.com {
	reverse_proxy 127.0.0.1:3000 {
		header_up Host {host}
	}
}

desk.hyerpath.com {
	reverse_proxy 127.0.0.1:3000 {
		header_up Host {host}
	}
}
