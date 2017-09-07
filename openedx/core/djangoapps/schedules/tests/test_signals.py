import datetime
from mock import patch
from pytz import utc

from course_modes.models import CourseMode
from course_modes.tests.factories import CourseModeFactory
from courseware.models import DynamicUpgradeDeadlineConfiguration
from openedx.core.djangoapps.schedules.signals import SCHEDULE_WAFFLE_FLAG
from openedx.core.djangoapps.site_configuration.tests.factories import SiteFactory
from openedx.core.djangoapps.waffle_utils.testutils import override_waffle_flag
from openedx.core.djangolib.testing.utils import skip_unless_lms
from student.models import CourseEnrollment
from student.tests.factories import CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from ..models import Schedule
from ..tests.factories import ScheduleConfigFactory


@patch('openedx.core.djangoapps.schedules.signals.get_current_site')
@skip_unless_lms
class CreateScheduleTests(SharedModuleStoreTestCase):

    def assert_schedule_created(self):
        course = _create_course_run(self_paced=True)
        enrollment = CourseEnrollmentFactory(course_id=course.id, mode=CourseMode.AUDIT)
        self.assertIsNotNone(enrollment.schedule)
        self.assertIsNone(enrollment.schedule.upgrade_deadline)

    def assert_schedule_not_created(self):
        course = _create_course_run(self_paced=True)
        enrollment = CourseEnrollmentFactory(course_id=course.id, mode=CourseMode.AUDIT)
        with self.assertRaises(Schedule.DoesNotExist):
            enrollment.schedule

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, True)
    def test_create_schedule(self, mock_get_current_site):
        site = SiteFactory.create()
        mock_get_current_site.return_value = site
        ScheduleConfigFactory.create(site=site)
        self.assert_schedule_created()

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, True)
    def test_no_current_site(self, mock_get_current_site):
        mock_get_current_site.return_value = None
        self.assert_schedule_not_created()

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, True)
    def test_schedule_config_disabled_waffle_enabled(self, mock_get_current_site):
        site = SiteFactory.create()
        mock_get_current_site.return_value = site
        ScheduleConfigFactory.create(site=site, create_schedules=False)
        self.assert_schedule_created()

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, False)
    def test_schedule_config_enabled_waffle_disabled(self, mock_get_current_site):
        site = SiteFactory.create()
        mock_get_current_site.return_value = site
        ScheduleConfigFactory.create(site=site, create_schedules=True)
        self.assert_schedule_created()

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, False)
    def test_schedule_config_disabled_waffle_disabled(self, mock_get_current_site):
        site = SiteFactory.create()
        mock_get_current_site.return_value = site
        ScheduleConfigFactory.create(site=site, create_schedules=False)
        self.assert_schedule_not_created()

    @override_waffle_flag(SCHEDULE_WAFFLE_FLAG, True)
    def test_schedule_config_creation_enabled_instructor_paced(self, mock_get_current_site):
        site = SiteFactory.create()
        mock_get_current_site.return_value = site
        ScheduleConfigFactory.create(site=site, enabled=True, create_schedules=True)
        course = _create_course_run(self_paced=False)
        enrollment = CourseEnrollmentFactory(course_id=course.id, mode=CourseMode.AUDIT)
        with self.assertRaises(Schedule.DoesNotExist):
            enrollment.schedule


@skip_unless_lms
class UpdateScheduleTests(SharedModuleStoreTestCase):
    ENABLED_SIGNALS = ['course_published']
    VERIFICATION_DEADLINE_DAYS = 14

    def setUp(self):
        super(UpdateScheduleTests, self).setUp()
        self.site = SiteFactory.create()
        ScheduleConfigFactory.create(site=self.site)
        DynamicUpgradeDeadlineConfiguration.objects.create(enabled=True, deadline_days=self.VERIFICATION_DEADLINE_DAYS)

    def assert_schedule_dates(self, schedule, expected_start):
        self.assertEquals(_strip_secs(schedule.start), _strip_secs(expected_start))
        self.assertEquals(
            _strip_secs(schedule.upgrade_deadline),
            _strip_secs(expected_start) + datetime.timedelta(days=self.VERIFICATION_DEADLINE_DAYS),
        )

    @patch('openedx.core.djangoapps.schedules.signals.get_current_site')
    def test_schedule_updated(self, mock_get_current_site):
        mock_get_current_site.return_value = self.site

        course = _create_course_run(self_paced=True, start_day_offset=5)
        enrollment = CourseEnrollmentFactory(course_id=course.id, mode=CourseMode.AUDIT)

        self.assert_schedule_dates(enrollment.schedule, enrollment.course_overview.start)

        course.start = course.start + datetime.timedelta(days=3)
        self.store.update_item(course, self.user.id)
        enrollment = CourseEnrollment.objects.get(id=enrollment.id)
        self.assert_schedule_dates(enrollment.schedule, course.start)

    @patch('openedx.core.djangoapps.schedules.signals.get_current_site')
    def test_schedule_not_updated(self, mock_get_current_site):
        mock_get_current_site.return_value = self.site

        course = _create_course_run(self_paced=True, start_day_offset=-5)
        enrollment = CourseEnrollmentFactory(course_id=course.id, mode=CourseMode.AUDIT)
        self.assert_schedule_dates(enrollment.schedule, enrollment.created)

        course.start = course.start + datetime.timedelta(days=3)
        self.store.update_item(course, self.user.id)
        self.assert_schedule_dates(enrollment.schedule, enrollment.created)


def _create_course_run(self_paced=True, start_day_offset=-1):
    """ Create a new course run and course modes.

    Both audit and verified `CourseMode` objects will be created for the course run.
    """
    now = datetime.datetime.now(utc)
    start = now + datetime.timedelta(days=start_day_offset)
    course = CourseFactory.create(start=start, self_paced=self_paced)

    CourseModeFactory(
        course_id=course.id,
        mode_slug=CourseMode.AUDIT
    )
    CourseModeFactory(
        course_id=course.id,
        mode_slug=CourseMode.VERIFIED,
        expiration_datetime=now + datetime.timedelta(days=100)
    )

    return course


def _strip_secs(timestamp):
    return timestamp.replace(second=0, microsecond=0)
