import urwid
from collections import OrderedDict
import logging

logger = logging.getLogger('urwid-log')


# FORM FIELDS

class FormField(urwid.Widget):
    creation_counter = 0

    def __init__(self, msg=None, **kwargs):
        if msg is None:
            msg = ''
            self.msg = None
        else:
            msg = self.msg = "%s " % msg
        self.creation_counter = FormField.creation_counter
        FormField.creation_counter += 1
        self.validators = kwargs.pop('validators', [])
        super(FormField, self).__init__(msg, **kwargs)

    def validate(self):
        for validator in self.validators:
            validator(self.value)


class TextField(FormField, urwid.Edit):
    @property
    def value(self):
        return self.edit_text


class NumberField(FormField, urwid.IntEdit):
    @property
    def value(self):
        try:
            return int(self.edit_text)
        except ValueError:
            raise ValueError("Must be a number!")


class BooleanField(FormField, urwid.CheckBox):
    @property
    def value(self):
        return self.get_state()


class SubmitField(FormField, urwid.Button):
    def __init__(self, *args, **kwargs):
        self.value = False
        super(SubmitField, self).__init__(*args, **kwargs)

    def render(self, *args, **kwargs):
        return urwid.Text("< %s >" % self.label).render(*args, **kwargs)

    def set_caption(self, *args, **kwargs):
        return super(SubmitField, self).set_label(*args, **kwargs)


# THE FORM THING

class FormMeta(urwid.widget.WidgetMeta):
    def __new__(cls, clsname, bases, attrs):
        fields = {}
        for name, attr in attrs.items():
            if isinstance(attr, FormField):
                if attr.msg is None:
                    attr.set_caption("%s: " % name)
                fields[name] = attr
        # fields = OrderedDict(sorted(fields.items(),
        #                             key=lambda (name, field): field.creation_counter))

        fields = OrderedDict(sorted(fields.items()))
        attrs['_fields'] = fields
        attrs['fields'] = fields
        return super(FormMeta, cls).__new__(cls, clsname, bases, attrs)


class FormErrorsBox(urwid.BoxAdapter):
    def selectable(self):
        return False


class Form(urwid.LineBox):
    __metaclass__ = FormMeta
    field_style = None
    focus_style = None
    error_style = None
    data = None
    fields = None
    _fields = {}
    errors = None
    form_errors = None

    def __init__(self, *args, **kwargs):
        self.data = {}

        self.fields = urwid.Pile([
            urwid.AttrMap(field, self.field_style, self.focus_style)
            for field in self._fields.values()])

        # self.fields = urwid.Pile([
        #     urwid.AttrMap(field, self.field_style, self.focus_style)
        #     for field in self.fields.values()])

        self.errors = urwid.Pile([
            urwid.AttrMap(urwid.Text(''), self.error_style)
            for _ in self.fields.contents])

        self.form_errors = urwid.SimpleListWalker([])
        form_errors = urwid.ListBox(self.form_errors)

        cols = urwid.Columns([self.fields, self.errors])

        whole = urwid.Pile([cols, FormErrorsBox(form_errors, 5)])

        if 'title' not in kwargs:
            kwargs['title'] = self.__class__.__name__
        super(Form, self).__init__(whole, **kwargs)

    def keypress(self, size, key):
        if key == 'enter':
            field = self.fields.get_focus().base_widget
            if isinstance(field, SubmitField):
                self._submit(field)
                return
            super(Form, self).keypress(size, 'down')
        return super(Form, self).keypress(size, key)

    def save(self):
        pass

    def _submit(self, field):
        field.value = True
        self.form_errors[:] = []
        errors = self._validate()
        if not errors:
            self.save()
        else:
            self.handle_errors(errors)
        field.value = False

    def _validate(self):
        errors = []
        for fieldname, (field, fw), (error_text, ew) in zip(self.fields,
                                                            self.fields.contents, self.errors.contents):
            try:
                field.base_widget.validate()
                error_text.base_widget.set_text('')
                self.data[fieldname] = field.base_widget.value
            except ValueError as e:
                errors.append(e.message)
                error_text.base_widget.set_text(e.message)
        try:
            self.validate()
        except ValueError as e:
            errors.append(e.message)
            self.form_errors.append(
                urwid.AttrMap(urwid.Text(e.message), self.error_style))
        return errors

    def validate(self):
        pass

    def handle_errors(self, errors):
        pass


# VALIDATORS

def includes(text, error_message=None):
    if error_message is None:
        error_message = "Must include %r!" % text

    def validator(value):
        if not text in value:
            raise ValueError(error_message)

    return validator


def lessthan(limit, error_message=None):
    if error_message is None:
        error_message = "Must be less than %d!" % limit

    def validator(value):
        if value >= limit:
            raise ValueError(error_message)

    return validator