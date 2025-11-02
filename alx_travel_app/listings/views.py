from django.shortcuts import render
from rest_framework import viewsets
from .models import Listing, Booking
from .serializers import ListingSerializer, BookingSerializer

class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    def perform_create(self, serializer):
        booking = serializer.save()
        # Trigger the Celery task asynchronously
        send_booking_email.delay(booking.id, booking.user.email)
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from .models import Booking, Payment
from .services.chapa_service import ChapaService
from .serializers import PaymentSerializer, BookingSerializer
import logging

logger = logging.getLogger(__name__)


class InitiatePaymentView(generics.GenericAPIView):
    """
    API endpoint to initiate payment for a booking
    POST /api/payments/initiate/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    
    def post(self, request):
        booking_id = request.data.get('booking_id')
        
        if not booking_id:
            return Response(
                {'error': 'booking_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the booking
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        
        # Check if payment already exists for this booking
        if hasattr(booking, 'payment') and booking.payment.status == 'completed':
            return Response(
                {'error': 'Payment already completed for this booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate transaction reference
        chapa = ChapaService(use_sandbox=True)
        tx_ref = chapa.generate_tx_ref(prefix='BOOKING')
        
        # Prepare payment URLs
        callback_url = request.build_absolute_uri(
            reverse('payment-callback')
        )
        return_url = request.build_absolute_uri(
            reverse('payment-success')
        )
        
        # Create or update payment record
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'booking_reference': str(booking.booking_reference),
                'transaction_id': tx_ref,
                'amount': booking.total_price,
                'currency': 'ETB',
                'email': request.user.email,
                'first_name': request.user.first_name or 'Customer',
                'last_name': request.user.last_name or 'User',
                'status': 'pending'
            }
        )
        
        if not created and payment.status == 'pending':
            # Update existing pending payment
            payment.transaction_id = tx_ref
            payment.save()
        
        # Initialize payment with Chapa
        chapa_response = chapa.initialize_payment(
            amount=float(booking.total_price),
            email=request.user.email,
            first_name=request.user.first_name or 'Customer',
            last_name=request.user.last_name or 'User',
            tx_ref=tx_ref,
            callback_url=callback_url,
            return_url=return_url,
            currency='ETB',
            customization={
                'title': 'Booking Payment',
                'description': f'Payment for booking {booking.booking_reference}'
            }
        )
        
        if chapa_response.get('status') == 'success':
            # Store Chapa reference
            payment.chapa_reference = chapa_response.get('data', {}).get('reference')
            payment.save()
            
            checkout_url = chapa_response.get('data', {}).get('checkout_url')
            
            return Response({
                'status': 'success',
                'message': 'Payment initiated successfully',
                'data': {
                    'transaction_id': tx_ref,
                    'checkout_url': checkout_url,
                    'payment_id': payment.id,
                    'amount': str(booking.total_price),
                    'currency': 'ETB'
                }
            }, status=status.HTTP_200_OK)
        else:
            payment.mark_as_failed(
                error_message=chapa_response.get('message', 'Payment initialization failed')
            )
            
            return Response({
                'status': 'error',
                'message': chapa_response.get('message', 'Payment initialization failed')
            }, status=status.HTTP_400_BAD_REQUEST)


class VerifyPaymentView(generics.GenericAPIView):
    """
    API endpoint to verify payment status
    GET /api/payments/verify/<tx_ref>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, tx_ref):
        # Get payment by transaction ID
        payment = get_object_or_404(Payment, transaction_id=tx_ref)
        
        # Verify with Chapa
        chapa = ChapaService(use_sandbox=True)
        verification_result = chapa.verify_payment(tx_ref)
        
        if verification_result.get('status') == 'success':
            data = verification_result.get('data', {})
            chapa_status = data.get('status', '').lower()
            
            # Update payment status
            if chapa_status == 'success':
                payment.mark_as_completed()
                payment.payment_method = data.get('payment_method', '')
                payment.metadata = data
                payment.save()
                
                # Send confirmation email (using Celery task)
                from .tasks import send_payment_confirmation_email
                send_payment_confirmation_email.delay(payment.id)
                
                return Response({
                    'status': 'success',
                    'message': 'Payment verified successfully',
                    'data': {
                        'payment_status': payment.status,
                        'transaction_id': payment.transaction_id,
                        'amount': str(payment.amount),
                        'booking_reference': payment.booking_reference
                    }
                }, status=status.HTTP_200_OK)
            
            elif chapa_status == 'pending':
                return Response({
                    'status': 'pending',
                    'message': 'Payment is still pending',
                    'data': {
                        'payment_status': payment.status,
                        'transaction_id': payment.transaction_id
                    }
                }, status=status.HTTP_200_OK)
            
            else:
                payment.mark_as_failed(
                    error_message=f"Payment failed with status: {chapa_status}"
                )
                
                return Response({
                    'status': 'failed',
                    'message': 'Payment verification failed',
                    'data': {
                        'payment_status': payment.status,
                        'transaction_id': payment.transaction_id
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
        
        else:
            return Response({
                'status': 'error',
                'message': verification_result.get('message', 'Verification failed')
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def payment_callback(request):
    """
    Webhook endpoint for Chapa payment callbacks
    POST /api/payments/callback/
    """
    
    try:
        # Get transaction reference from callback
        tx_ref = request.data.get('tx_ref') or request.data.get('trx_ref')
        
        if not tx_ref:
            logger.error("No transaction reference in callback")
            return Response({'status': 'error'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment
        payment = Payment.objects.filter(transaction_id=tx_ref).first()
        
        if not payment:
            logger.error(f"Payment not found for tx_ref: {tx_ref}")
            return Response({'status': 'error'}, status=status.HTTP_404_NOT_FOUND)
        
        # Verify payment with Chapa
        chapa = ChapaService(use_sandbox=True)
        verification_result = chapa.verify_payment(tx_ref)
        
        if verification_result.get('status') == 'success':
            data = verification_result.get('data', {})
            chapa_status = data.get('status', '').lower()
            
            if chapa_status == 'success':
                payment.mark_as_completed()
                payment.payment_method = data.get('payment_method', '')
                payment.metadata = data
                payment.save()
                
                # Send confirmation email
                from .tasks import send_payment_confirmation_email
                send_payment_confirmation_email.delay(payment.id)
                
                logger.info(f"Payment completed: {tx_ref}")
            else:
                payment.mark_as_failed(
                    error_message=f"Payment status: {chapa_status}"
                )
                logger.warning(f"Payment failed: {tx_ref}, status: {chapa_status}")
        
        return Response({'status': 'success'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in payment callback: {str(e)}")
        return Response({'status': 'error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def payment_success(request):
    """
    Success page endpoint after payment completion
    GET /api/payments/success/
    """
    
    tx_ref = request.GET.get('tx_ref') or request.GET.get('trx_ref')
    
    if not tx_ref:
        return Response({
            'status': 'error',
            'message': 'No transaction reference provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    payment = Payment.objects.filter(transaction_id=tx_ref).first()
    
    if not payment:
        return Response({
            'status': 'error',
            'message': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    return Response({
        'status': 'success',
        'message': 'Payment processed',
        'data': {
            'payment_status': payment.status,
            'transaction_id': payment.transaction_id,
            'booking_reference': payment.booking_reference,
            'amount': str(payment.amount)
        }
    }, status=status.HTTP_200_OK)


class PaymentListView(generics.ListAPIView):
    """
    List all payments for the authenticated user
    GET /api/payments/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    
    def get_queryset(self):
        return Payment.objects.filter(
            booking__user=self.request.user
        ).select_related('booking', 'booking__listing')