import json
import logging
import stripe
import httpx
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentSerializer
from uuid import UUID


logger = logging.getLogger(__name__)


stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentCreateView(APIView):
	def post(self, request):
		serializer = PaymentCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		reservation_id = serializer.validated_data['reservation_id']

		# Fetch amount from Booking Service
		try:
			rid = UUID(str(reservation_id))
		except Exception:
			return Response({"error": "Invalid reservation_id"}, status=status.HTTP_400_BAD_REQUEST)

		try:
			with httpx.Client(timeout=5.0) as client:
				r = client.get(f"{settings.BOOKING_BASE_URL}/api/v1/reservations/{rid}/payment-info/")
			if r.status_code != 200:
				return Response({"error": "Unable to fetch reservation", "detail": r.text}, status=status.HTTP_400_BAD_REQUEST)
			booking_data = r.json()
			amount_cents = int(booking_data.get('amount_cents', 0))
			reservation_status = str(booking_data.get('status', '')).upper()
		except Exception as exc:  # noqa: BLE001
			return Response({"error": "Booking lookup failed", "detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

		if amount_cents <= 0:
			return Response({"error": "Invalid amount from reservation"}, status=status.HTTP_400_BAD_REQUEST)

		# Block duplicate/invalid payments based on reservation status
		if reservation_status in {"PAID", "CONFIRMED"}:
			return Response({"error": "Reservation is already paid/confirmed"}, status=status.HTTP_400_BAD_REQUEST)
		if reservation_status in {"CANCELLED", "EXPIRED"}:
			return Response({"error": "Reservation is not payable (cancelled/expired)"}, status=status.HTTP_400_BAD_REQUEST)

		payment = Payment.objects.create(
			reservation_id=reservation_id,
			amount_cents=amount_cents,
			status='PENDING'
		)

		# Optional override of success/cancel URLs (neutral defaults that don't hit gateway)
		success_url = request.data.get('success_url') or 'https://example.com/success?reservation_id={RES}'
		cancel_url = request.data.get('cancel_url') or 'https://example.com/cancel?reservation_id={RES}'
		success_url = success_url.replace('{RES}', str(reservation_id))
		cancel_url = cancel_url.replace('{RES}', str(reservation_id))

		try:
			session = stripe.checkout.Session.create(
				mode='payment',
				payment_method_types=['card'],
				line_items=[{
					'price_data': {
						'currency': 'usd',
						'unit_amount': amount_cents,
						'product_data': {
							'name': f'Reservation {reservation_id}',
						},
					},
					'quantity': 1,
				}],
				success_url=success_url,
				cancel_url=cancel_url,
				payment_intent_data={
					'metadata': {
						'reservation_id': str(reservation_id),
						'payment_id': str(payment.id),
					}
				},
				metadata={
					'reservation_id': str(reservation_id),
					'payment_id': str(payment.id),
				},
			)
		except stripe.error.StripeError as exc:  # noqa: BLE001
			payment.status = 'FAILED'
			payment.provider_payload = {'error': str(exc)}
			payment.save(update_fields=['status', 'provider_payload'])
			return Response({'error': 'Stripe error', 'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

		# Session may include a payment_intent ID immediately; store what we have
		payment.stripe_payment_intent = session.get('payment_intent')
		session_payload = session.to_dict_recursive() if hasattr(session, 'to_dict_recursive') else session
		payment.provider_payload = session_payload
		payment.save(update_fields=['stripe_payment_intent', 'provider_payload'])

		return Response(
			{
				'payment_id': str(payment.id),
				'client_secret': None,
				'checkout_url': session.get('url'),
			},
			status=status.HTTP_201_CREATED
		)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
	authentication_classes = []
	permission_classes = []

	def post(self, request):
		payload = request.body
		sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

		try:
			event = stripe.Webhook.construct_event(
				payload=payload,
				sig_header=sig_header,
				secret=settings.STRIPE_WEBHOOK_SECRET
			)
		except ValueError:
			logger.warning("Stripe webhook: invalid payload")
			return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)
		except stripe.error.SignatureVerificationError:
			logger.warning("Stripe webhook: signature verification failed. Check STRIPE_WEBHOOK_SECRET on server matches the CLI/listener.")
			return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

		if event['type'] == 'payment_intent.succeeded':
			pi = event['data']['object']
			reservation_id = pi['metadata'].get('reservation_id')
			payment_intent_id = pi['id']
			payment_id = pi['metadata'].get('payment_id')
			pi_payload = pi.to_dict_recursive() if hasattr(pi, 'to_dict_recursive') else pi

			updated = Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(
				status='SUCCEEDED',
				provider_payload=pi_payload,
			)
			if updated == 0 and payment_id:
				try:
					Payment.objects.filter(id=payment_id).update(
						status='SUCCEEDED',
						provider_payload=pi_payload,
						stripe_payment_intent=payment_intent_id,
					)
				except Exception:
					logger.warning("Webhook PI succeeded: payment record not found", extra={"payment_id": payment_id, "payment_intent": payment_intent_id})

			# Notify Booking to confirm the reservation
			booking_url = f"{settings.BOOKING_BASE_URL}/api/v1/reservations/{reservation_id}/confirm/"
			try:
				with httpx.Client(timeout=5.0) as client:
					resp = client.post(booking_url, json={'payment_intent_id': payment_intent_id})
				if resp.status_code >= 400:
					Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(status='FAILED')
					logger.warning("Booking confirm failed after PI succeeded", extra={"status": resp.status_code, "body": resp.text})
			except Exception:
				Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(status='FAILED')
				logger.warning("Booking confirm error after PI succeeded", exc_info=True)

		elif event['type'] == 'checkout.session.completed':
			session = event['data']['object']
			payment_intent_id = session.get('payment_intent')
			# Retrieve PI to read metadata (set via payment_intent_data.metadata)
			try:
				pi = stripe.PaymentIntent.retrieve(payment_intent_id)
				reservation_id = pi['metadata'].get('reservation_id')
				payment_id = pi['metadata'].get('payment_id')
			except Exception:
				reservation_id = None
				payment_id = None

			# Mark success and notify booking
			if payment_intent_id and reservation_id:
				payload_dict = session.to_dict_recursive() if hasattr(session, 'to_dict_recursive') else session
				updated = Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(
					status='SUCCEEDED',
					provider_payload=payload_dict,
				)
				if updated == 0 and payment_id:
					Payment.objects.filter(id=payment_id).update(
						status='SUCCEEDED',
						provider_payload=payload_dict,
						stripe_payment_intent=payment_intent_id,
					)
				booking_url = f"{settings.BOOKING_BASE_URL}/api/v1/reservations/{reservation_id}/confirm/"
				try:
					with httpx.Client(timeout=5.0) as client:
						resp = client.post(booking_url, json={'payment_intent_id': payment_intent_id})
					if resp.status_code >= 400:
						Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(status='FAILED')
				except Exception:
					Payment.objects.filter(stripe_payment_intent=payment_intent_id).update(status='FAILED')

		return Response({'status': 'ok'}, status=status.HTTP_200_OK)
