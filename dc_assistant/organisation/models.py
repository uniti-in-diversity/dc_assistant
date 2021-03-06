from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.core.validators import MaxValueValidator, MinValueValidator
from taggit.managers import TaggableManager
from extend.models import TaggedItem, ImgAttach, LoggingModel
from extend.forms import ColorField
from django.core.exceptions import ValidationError
from smart_selects.db_fields import ChainedForeignKey


class Region(MPTTModel):
    """
    Country/Regin/City where place location. Every instance of this class can be parent for the other one
    """
    parent = TreeForeignKey(
        to='self',
        on_delete=models.CASCADE,
        related_name='children',
        blank=True,
        null=True,
        db_index=True
    )
    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(
        unique=True
    )
    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?region={}".format(reverse('organisation:location_list'), self.slug)

class Location(LoggingModel):
    """
    The place where located IT infrastructure (Build, Office, DC and so on)
    """
    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(
        unique=True
    )
    region = models.ForeignKey(
        to=Region,
        on_delete=models.SET_NULL,
        related_name='locations',
        blank=True,
        null=True
    )
    physical_address = models.CharField(
        max_length=200,
        blank=True
    )
    description = models.CharField(
        max_length=100,
        blank=True
    )
    comment = models.TextField(
        blank=True
    )
    tag = TaggableManager(
        through=TaggedItem
    )

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('organisation:location', args=[self.slug])

class Rack(LoggingModel):
    """
    Rack configuration
    """
    TYPE_1FRAME = '1-frame'
    TYPE_2FRAME = '2-frame'
    TYPE_WALLCABINET = 'wall-cabinet'
    TYPE_FLOORCABINET = 'floor-cabinet'

    TOP_TO_BUTTOM = 0
    BUTTOM_TO_TOP = 1


    RACK_TYPE_CHOICES = (
        (TYPE_1FRAME, 'One Frame rack'),
        (TYPE_2FRAME, 'Two Frame rack'),
        (TYPE_WALLCABINET, 'Wall-mounted cabinet'),
        (TYPE_FLOORCABINET, 'Floor-mounted cabinet'),
    )
    RACK_UNIT_DESC = (
        (TOP_TO_BUTTOM, 'Top to buttom'),
        (BUTTOM_TO_TOP, 'Buttom to top'),
    )
    name = models.CharField(
        max_length=50
    )
    location = models.ForeignKey(
        to=Location,
        on_delete=models.PROTECT,
        related_name='racks'
    )
    u_height = models.PositiveSmallIntegerField(
        default=44,
        verbose_name='Unit Height',
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    desc_units = models.BooleanField(
        choices=RACK_UNIT_DESC,
        default=BUTTOM_TO_TOP,
        verbose_name='Orientation',
        help_text='Default buttom to top'
    )
    racktype = models.CharField(
        max_length=50,
        choices=RACK_TYPE_CHOICES,
        default=TYPE_FLOORCABINET,
    )
    comment = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ('location', 'name', 'pk')

    def __str__(self):
        return self.name

    # def __str__(self):
    #     return self.display_name or super().__str__()

    def get_absolute_url(self):
        return reverse('organisation:rack', args=[self.pk])

    # @property
    # def display_name(self):
    #     if self.location:
    #         return "{} ({})".format(self.name, self.location)
    #     elif self.name:
    #         return self.name
    #     return ""

class Vendor(LoggingModel):
    """
    Device`s vendors
    """
    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(
        unique=True
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?vendor={}".format(reverse('organisation:model_list'), self.slug)

class VendorModel(LoggingModel):
    """
    Vendor models of device
    """
    vendor = models.ForeignKey(
        to=Vendor,
        on_delete=models.PROTECT,
        related_name='device_models'
    )
    model = models.CharField(
        max_length=50
    )
    slug = models.SlugField(
        unique=True
    )
    u_height = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Height (U)'
    )
    depth = models.BooleanField(
        default=True,
        verbose_name='Full Depth',
        help_text='Default is Full Depth'
    )
    front_image = models.ImageField(
        upload_to='imgs-devicemodel',
        blank=True
    )
    rear_image = models.ImageField(
        upload_to='imgs-devicemodel',
        blank=True
    )
    comment = models.TextField(
        blank=True
    )
    # def get_absolute_url(self):
    #     return reverse('organisation:vendormodel', args=[self.pk])
    @property
    def display_name(self):
        return '{} {}'.format(self.vendor.name, self.model)

    def __str__(self):
        return '{} {}'.format(self.vendor.name, self.model)


class Platform(LoggingModel):
    """
    Platform is software or firmware running on the devices
    """

    name = models.CharField(
        max_length=100,
        unique=True
    )
    slug = models.SlugField(
        unique=True,
        max_length=100
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return "{}?platform={}".format(reverse('organisation:device_list'), self.slug)


class DeviceRole(LoggingModel):
    """
    Role of device or vm or service. For example device can be group by funcionality role (file server, mail server)
    """

    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(
        unique=True
    )
    description = models.CharField(
        max_length=100,
        blank=True
    )
    color = ColorField()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Device(LoggingModel):
    """
    Device instance with. Each device must be assigned to location and can be place to rack.
    """

    #TODO: добавить обьединение в кластер, генерация IP адресов

    FRONT = 1
    REAR = 0

    RACK_SIDE_CHOICES = (
        (FRONT, 'Located at the front of rack'),
        (REAR, 'Located at the rear of rack'),
    )

    name = models.CharField(
        max_length=50,
        unique=True
    )
    device_model = models.ForeignKey(
        to=VendorModel,
        on_delete=models.PROTECT,
        related_name='instances'
    )
    device_role = models.ForeignKey(
        to=DeviceRole,
        on_delete=models.PROTECT,
        related_name='devices'
    )
    platform = models.ForeignKey(
        to=Platform,
        on_delete=models.SET_NULL,
        related_name='devices',
        blank=True,
        null=True
    )
    serial = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Serial number'
    )
    location = models.ForeignKey(
        to=Location,
        on_delete=models.PROTECT,
        related_name='devices'
    )
    rack = models.ForeignKey(
        to=Rack,
        on_delete=models.PROTECT,
        related_name='devices',
        blank=True,
        null=True
    )
    position = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
        verbose_name='Unit Number',
        help_text='Unit Number device starts location in the rack'
    )
    face_position = models.PositiveSmallIntegerField(
        choices=RACK_SIDE_CHOICES,
        default=FRONT,
        blank=True,
        null=True
    )
#    cluster = models.ForeignKey(
#        to='Cluster',
#        on_delete=models.SET_NULL,
#        related_name='devices',
#        blank=True,
#        null=True
#    )
#    primary_ip = models.OneToOneField(
#        to='IPAddress',
#        on_delete=models.SET_NULL,
#        related_name='primary_ip',
#        blank=True,
#        null=True,
#        verbose_name='Основной IP адрес'
#    )
    description = models.CharField(
        max_length=100,
        blank=True
    )
    comment = models.TextField(
        blank=True
    )
    images = GenericRelation(
        to=ImgAttach
    )
    tag = TaggableManager(
        through=TaggedItem
    )

    class Meta:
        ordering = ('name', 'pk')

    def __str__(self):
        return self.display_name or super().__str__()
        return self.name

    @property
    def display_name(self):
        if self.name:
            return self.name
        elif hasattr(self, 'device_model'):
            return "{}".format(self.device_model)
        return ""

    def get_absolute_url(self):
        return reverse('organisation:device', args=[self.pk])

    def clean(self):

        super().clean()

        if self.rack is None:
            if self.position:
                raise ValidationError({
                    'position': "Cannot select position without rack selected.",
                })
            if self.face_position:
                raise ValidationError({
                    'face_position': "Cannot select face_position without rack selected.",
                })


