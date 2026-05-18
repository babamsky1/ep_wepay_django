from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import DatabaseError
from django.db import connection
import json
import logging
import os


@csrf_exempt
@require_POST
def login_view(request):
    # Login API for employee system
    # Accepts POST request only

    try:
        # Convert JSON body to python dict
        data = json.loads(request.body)

        email_address = data.get('email_address')
        password = data.get('password')

        # Required fields validation
        if not email_address or not password:
            return JsonResponse(
                {'error': 'Email and password required'},
                status=400
            )

        # Check superadmin credentials from .env
        superadmin_email = os.environ.get('SUPERADMIN_EMAIL')
        superadmin_password = os.environ.get('SUPERADMIN_PASSWORD')
        superadmin_first_name = os.environ.get('SUPERADMIN_FIRST_NAME', 'Super')
        superadmin_last_name = os.environ.get('SUPERADMIN_LAST_NAME', 'Admin')

        if email_address == superadmin_email and password == superadmin_password:
            return JsonResponse(
                {
                    'success': True,
                    'user': {
                        'emp_id': 'SUPERADMIN',
                        'email': email_address,
                        'name': f"{superadmin_first_name} {superadmin_last_name}".strip(),
                        'role': 'superadmin',
                        'has_lastpay_access': True
                    }
                }
            )

        with connection.cursor() as cursor:

            # Check if matching email + password exists
            cursor.execute(
                """
                SELECT
                    emp_id,
                    email_address,
                    first_name,
                    last_name,
                    role_id,
                    system_access
                FROM employee
                WHERE email_address = %s
                AND system_password = %s
                """,
                [email_address, password]
            )

            employee = cursor.fetchone()

        # If account found
        if employee:

            (
                emp_id,
                email,
                first_name,
                last_name,
                role_id,
                system_access
            ) = employee

            # Check if may system access pa
            if system_access != 'Y':
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'Invalid email or password'
                    },
                    status=403
                )

            # Convert role_id to readable role name
            role_map = {
                1: 'superadmin',
                2: 'finance',
                3: 'hr',
                4: 'manager'
            }

            user_role = role_map.get(role_id, 'employee')

            # Success login response
            return JsonResponse(
                {
                    'success': True,
                    'user': {
                        'emp_id': emp_id,
                        'email': email,
                        'name': f"{first_name} {last_name}".strip(),
                        'role': user_role,

                        # For future access control
                        'has_lastpay_access': True
                    }
                }
            )

        # No matching user found
        return JsonResponse(
            {
                'success': False,
                'error': 'Invalid credentials'
            },
            status=401
        )

    except json.JSONDecodeError:
        # Bad JSON request body
        return JsonResponse(
            {'error': 'Invalid request format'},
            status=400
        )

    except DatabaseError:
        # DB issue
        logger = logging.getLogger(__name__)

        logger.error("Database error during authentication")

        return JsonResponse(
            {'error': 'Authentication service unavailable'},
            status=503
        )

    except Exception as e:
        # Unexpected issue
        logger = logging.getLogger(__name__)

        logger.error(f"Unexpected error in login_view: {str(e)}")

        return JsonResponse(
            {'error': 'Authentication failed'},
            status=500
        )
