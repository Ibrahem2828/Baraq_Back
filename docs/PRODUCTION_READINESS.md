# Production Readiness Status

## ما تم إغلاقه في هذه النسخة

- حذف طبقات AI المدمجة القديمة وإبقاء integration layer فقط.
- إزالة الأسرار وقواعد البيانات والملفات المؤقتة من الحزمة.
- إصلاح تعريفات مكررة وأخطاء URL router.
- API v1 موحد مع legacy compatibility.
- صفحات root و404 و500 بشرية، وأخطاء API بصيغة JSON.
- JWT rotation/blacklist وthrottling.
- فصل liveness عن readiness.
- PostgreSQL + Redis + Celery + non-root Docker image.
- Upload validation وOffice archive safety checks.
- AI Jobs idempotency، credits reserve/refund، webhook HMAC، وحماية terminal states.
- Materialization لجميع شخصيات برّاق.
- RBAC للداشبورد، دعم، إشعارات، وإدارة المحتوى.
- اختبارات محدثة للتدفقات الرئيسية.

## بوابة الإطلاق الإلزامية

لا يعتمد الإصدار إنتاجياً قبل نجاح التالي داخل Staging مطابق للإنتاج:

```bash
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test
python manage.py spectacular --file openapi.yaml --validate
```

ثم:

- Docker build دون warnings مانعة.
- database backup/restore drill.
- upload tests للأنواع المدعومة والملفات الخبيثة.
- concurrent credits/idempotency tests.
- AI webhook replay/signature tests.
- end-to-end من الجوال إلى AI ثم materialization.
- dashboard RBAC matrix.
- load test لنقاط login/list/upload/jobs.
- HTTPS وCORS وsecurity headers audit.

## ما لا يمكن ضمانه بالفحص الساكن

الفحص الساكن يثبت سلامة syntax والبنية وعدم وجود تعريفات مكررة أو ملفات محظورة وفق القواعد، لكنه لا يثبت توافق dependencies أو migrations أو الشبكة أو مزود التخزين أو AI service. هذه الأمور تتطلب بناء الحاويات وتشغيل Staging.
