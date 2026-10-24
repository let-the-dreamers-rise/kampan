# AWS Lambda container image: Python 3.12 runtime with OpenCV 5.0.0 (headless).
FROM public.ecr.aws/lambda/python:3.12

COPY requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir --progress-bar off --timeout 60 --retries 3 -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt --target ${LAMBDA_TASK_ROOT} \
 && python -c "import sys; sys.path.insert(0, '${LAMBDA_TASK_ROOT}'); import cv2; assert cv2.__version__.startswith('5.'), cv2.__version__"

# Passkey sign-in libraries, in their own layer so the OpenCV layer above stays cached.
COPY requirements-auth.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir --progress-bar off --timeout 60 --retries 3 -r ${LAMBDA_TASK_ROOT}/requirements-auth.txt --target ${LAMBDA_TASK_ROOT} \
 && python -c "import sys; sys.path.insert(0, '${LAMBDA_TASK_ROOT}'); import webauthn, cryptography"

COPY kampan ${LAMBDA_TASK_ROOT}/kampan
COPY app ${LAMBDA_TASK_ROOT}/app

CMD ["app.handler.handler"]
