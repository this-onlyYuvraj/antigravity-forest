"""
Notification Service for Alert Dispatch
Handles SMS (Twilio) and Email (SendGrid) notifications
"""

from loguru import logger
from config import config
from typing import Dict, Any, List

# Uncomment these imports when you have API credentials:
# from twilio.rest import Client
# from sendgrid import SendGridAPIClient
# from sendgrid.helpers.mail import Mail


class NotificationService:
    """
    Notification dispatcher for tiered alert system
    
    NOTE: SMS and Email sending is commented out by default.
    Uncomment when you have API credentials configured.
    """
    
    def __init__(self):
        self.sms_enabled = False
        self.email_enabled = False
        
        # Uncomment to enable SMS (requires Twilio account):
        # if config.TWILIO_ACCOUNT_SID and config.TWILIO_AUTH_TOKEN:
        #     self.twilio_client = Client(
        #         config.TWILIO_ACCOUNT_SID,
        #         config.TWILIO_AUTH_TOKEN
        #     )
        #     self.sms_enabled = True
        #     logger.info("✓ SMS notifications enabled (Twilio)")
        # else:
        #     logger.warning("SMS notifications disabled (no Twilio credentials)")
        
        # Uncomment to enable Email (requires SendGrid account):
        # if config.SENDGRID_API_KEY:
        #     self.sendgrid_client = SendGridAPIClient(config.SENDGRID_API_KEY)
        #     self.email_enabled = True
        #     logger.info("✓ Email notifications enabled (SendGrid)")
        # else:
        #     logger.warning("Email notifications disabled (no SendGrid credentials)")
        
        logger.info("Notification service initialized (using on-screen alerts only)")
    
    def send_tier2_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send priority alert for Tier 2 (Protected Areas)
        
        Original behavior: Immediate SMS dispatch
        Current behavior: Log to console (actual sending commented out)
        
        Args:
            alert: Alert data dictionary
        
        Returns:
            True if notification was sent (or logged) successfully
        """
        logger.warning("=" * 80)
        logger.warning("🚨 TIER 2 PRIORITY ALERT - PROTECTED AREA")
        logger.warning("=" * 80)
        logger.warning(f"Alert ID: {alert.get('id', 'N/A')}")
        logger.warning(f"Detection Date: {alert.get('detection_date', 'N/A')}")
        logger.warning(f"Confidence: {alert.get('confidence_score', 0) * 100:.1f}%")
        logger.warning(f"Area: {alert.get('area_hectares', 0):.2f} ha")
        logger.warning(f"Location: {alert.get('boundary_name', 'Unknown')}")
        logger.warning(f"VH Drop: {alert.get('alt_vh_drop_db', 0):.2f} dB")
        logger.warning(f"VV Drop: {alert.get('alt_vv_drop_db', 0):.2f} dB")
        logger.warning("=" * 80)
        
        # COMMENTED OUT: Uncomment when you have Twilio credentials
        # if self.sms_enabled:
        #     try:
        #         message = self.twilio_client.messages.create(
        #             body=f"🚨 PRIORITY DEFORESTATION ALERT\n"
        #                  f"Area: {alert.get('area_hectares', 0):.2f} ha\n"
        #                  f"Location: {alert.get('boundary_name', 'Protected Area')}\n"
        #                  f"Confidence: {alert.get('confidence_score', 0) * 100:.1f}%\n"
        #                  f"Alert ID: {alert.get('id', 'N/A')}",
        #             from_=config.TWILIO_PHONE_NUMBER,
        #             to=config.ALERT_SMS_RECIPIENT
        #         )
        #         logger.success(f"✓ SMS sent: {message.sid}")
        #         return True
        #     except Exception as e:
        #         logger.error(f"Failed to send SMS: {e}")
        #         return False
        # else:
        #     logger.info("SMS sending skipped (not enabled)")
        #     return True
        
        return True  # Always return True for logging-only mode
    
    def send_tier1_digest(self, alerts: List[Dict[str, Any]]) -> bool:
        """
        Send email digest for Tier 1 (Standard) alerts
        
        Original behavior: Email digest after 2nd confirmation
        Current behavior: Log to console (actual sending commented out)
        
        Args:
            alerts: List of alert data dictionaries
        
        Returns:
            True if notification was sent (or logged) successfully
        """
        if not alerts:
            return True
        
        logger.info("=" * 80)
        logger.info(f"📧 TIER 1 ALERT DIGEST ({len(alerts)} alerts)")
        logger.info("=" * 80)
        
        for idx, alert in enumerate(alerts, 1):
            logger.info(f"Alert {idx}:")
            logger.info(f"  ID: {alert.get('id', 'N/A')}")
            logger.info(f"  Date: {alert.get('detection_date', 'N/A')}")
            logger.info(f"  Area: {alert.get('area_hectares', 0):.2f} ha")
            logger.info(f"  Confidence: {alert.get('confidence_score', 0) * 100:.1f}%")
        
        logger.info("=" * 80)
        
        # COMMENTED OUT: Uncomment when you have SendGrid credentials
        # if self.email_enabled:
        #     try:
        #         # Build HTML email content
        #         html_content = self._build_digest_html(alerts)
        #         
        #         message = Mail(
        #             from_email=config.ALERT_EMAIL_FROM,
        #             to_emails=config.ALERT_EMAIL_RECIPIENT,
        #             subject=f'Deforestation Alert Digest - {len(alerts)} New Alerts',
        #             html_content=html_content
        #         )
        #         
        #         response = self.sendgrid_client.send(message)
        #         logger.success(f"✓ Email sent: {response.status_code}")
        #         return True
        #     except Exception as e:
        #         logger.error(f"Failed to send email: {e}")
        #         return False
        # else:
        #     logger.info("Email sending skipped (not enabled)")
        #     return True
        
        return True  # Always return True for logging-only mode
    
    def _build_digest_html(self, alerts: List[Dict[str, Any]]) -> str:
        """Build HTML email content for alert digest"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .alert {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; }}
                .tier2 {{ border-left: 5px solid #ef4444; }}
                .tier1 {{ border-left: 5px solid #f97316; }}
            </style>
        </head>
        <body>
            <h1>Deforestation Alert Digest</h1>
            <p>{len(alerts)} new alerts detected in Novo Progresso, Pará</p>
        """
        
        for alert in alerts:
            tier_class = 'tier2' if alert.get('risk_tier') == 'TIER_2' else 'tier1'
            html += f"""
            <div class="alert {tier_class}">
                <h3>Alert #{alert.get('id', 'N/A')}</h3>
                <p><strong>Area:</strong> {alert.get('area_hectares', 0):.2f} ha</p>
                <p><strong>Confidence:</strong> {alert.get('confidence_score', 0) * 100:.1f}%</p>
                <p><strong>Location:</strong> {alert.get('boundary_name', 'Novo Progresso')}</p>
                <p><strong>Detection:</strong> {alert.get('detection_date', 'N/A')}</p>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        return html


# Global notification service instance
notification_service = NotificationService()


if __name__ == "__main__":
    """Test notification service"""
    import sys
    from loguru import logger
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Test Tier 2 alert
    test_alert = {
        'id': 123,
        'detection_date': '2026-01-29',
        'confidence_score': 0.92,
        'area_hectares': 2.5,
        'boundary_name': 'Terra Indígena Baú',
        'alt_vh_drop_db': -2.4,
        'alt_vv_drop_db': -2.1,
    }
    
    logger.info("Testing Tier 2 notification...")
    notification_service.send_tier2_alert(test_alert)
    
    logger.info("\nTesting Tier 1 digest...")
    notification_service.send_tier1_digest([test_alert])
