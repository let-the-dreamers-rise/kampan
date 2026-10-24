# AWS Lambda container image: Python 3.12 runtime with OpenCV 5.0.0 (headless).
FROM public.ecr.aws/lambda/python:3.12

COPY requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt --target ${LAMBDA_TASK_ROOT} \
 && python -c "import sys; sys.path.insert(0, '${LAMBDA_TASK_ROOT}'); import cv2; assert cv2.__version__.startswith('5.'), cv2.__version__"

COPY kampan ${LAMBDA_TASK_ROOT}/kampan
COPY app ${LAMBDA_TASK_ROOT}/app

CMD ["app.handler.handler"]
