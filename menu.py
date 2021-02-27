# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from typing import Any, List, Dict
from urwid import AttrMap, Columns, ListBox, RadioButton, Text, Widget, WidgetWrap, connect_signal, emit_signal, \
    register_signal, ListWalker, CompositeCanvas
from interface import ApplicationHandler, WidgetDrawer


class MenuItem(Text):
    """
    Standard MenuItem enhances Text Widget by signal 'activate'
    """
    application: ApplicationHandler = None
    
    def __init__(self, id, caption, description: Any = None, app: ApplicationHandler = None):
        Text.__init__(self, caption)
        self.id = id
        self.description = description
        register_signal(self.__class__, ['activate'])
        self.application = app
    
    def keypress(self, size, key: str = '') -> str:
        if key == 'enter':
            emit_signal(self, 'activate', key)
        else:
            if self.application is not None:
                if not key in ['c', 'esc']:
                    self.application.handle_event(key)
            return key
    
    def get_id(self) -> int:
        return self.id
    
    def get_description(self) -> str:
        return self.description
    
    def selectable(self):
        return True


class MultiRadioButton(RadioButton):
    """
    Enhances RadioButton with content columns and ability to have a parent.
    """
    _parent: WidgetDrawer = None
    
    def __init__(self, group: List[Widget], id: int, label: Any, column_content: List[Widget],
                 state: bool = "first True", on_state_change: Any = None, user_data: Any = None):
        self.id = id
        self.column_content = column_content
        # register_signal(self.__class__, ['activate'])
        super(MultiRadioButton, self).__init__(group, label, state, on_state_change, user_data)
    
    def selectable(self):
        return True
    
    def get_id(self) -> int:
        return self.id
    
    def get_column_content(self) -> List[Widget]:
        return self.column_content
    
    def trigger_multi_menu_item_redraw(self, event):
        self._parent.refresh_content(event)
    
    @property
    def parent(self):
        return self._parent
    
    @parent.setter
    def parent(self, parent: WidgetDrawer):
        self._parent = parent
    
    @parent.deleter
    def parent(self):
        del self._parent


class MultiMenuItem(WidgetDrawer):
    """
    Enhanced MultiRadioButton with focus handling etc.
    """
    application: ApplicationHandler = None
    dirty: bool = True
    parent_listbox: ListBox = None
    last_focus: int = -1
    current_focus: int = 0
    _state: bool = False
    
    def __init__(self, group: List[MultiRadioButton], id: int, label: Any, column_content: List[Widget],
                 state: Any = "first True", on_state_change: Any = None, user_data: Any = None,
                 app: ApplicationHandler = None):
        self._group = group
        self._id = id
        self._label = label
        self._column_content = column_content
        if type(state) is str:
            if str(state).lower() == 'first true':
                if self._id == 1:
                    self._state = True
        else:
            self._state = state
        self._on_state_change = on_state_change
        self._user_data = user_data
        self.application = app
        self._selectable = True
        select_on: int = self.get_selected_id()
        if select_on is not None:
            self._state = True if select_on == self._id else False
        if len(self._group) >= self._id:
            del self._group[self._id - 1]  # remove old MMI from self._group
        self._hidden_widget: MultiRadioButton = MultiRadioButton(self._group, self._id, self._label,
                                                                 self._column_content, self._state,
                                                                 self._on_state_change, self._user_data)
        self._hidden_widget.parent = self
        connect_signal(self._hidden_widget, 'change', self.handle_changed)
        self.display_widget = self._create_display_widget()
        super(MultiMenuItem, self).__init__(self.display_widget)
        register_signal(self.__class__, ['change', 'postchange'])
        connect_signal(self, 'change', self.mark_as_dirty)
    
    def _create_display_widget(self, event: Any = None) -> Columns:
        """
        Returns the Columns Widget needed to draw the wrapped Widget every event.
        
        :param event: The event to be drawn by.
        :return: The columns to be rendered.
        """
        focus_on: int = self.get_focus_id(event)
        if focus_on == self._id:
            self._focus = True
        else:
            self._focus = False
        color: str = 'MMI.focus' if self._focus else 'MMI.selectable'
        self.display_widget: Columns = Columns([
            ('weight', 1, AttrMap(self._hidden_widget, 'MMI.selectable', 'MMI.focus')),
            ('weight', 4, AttrMap(self._column_content, color, color)),
        ])
        return self.display_widget
    
    def get_focus_id(self, event: Any = None) -> int:
        """
        Returns the id starting by 1 of the item holding the current focus.
        
        :param event: The current event.
        :return: The id of the focused item (1+)
        """
        focus_on: int = 1
        if self.parent_listbox is None:
            focus_on = 1
        else:
            if event is None:
                event = 'no event'
            focus_on = self.application.get_focused_menu(self.parent_listbox, event)
        return focus_on
    
    def mark_as_dirty(self, event: Any = None):
        """
        Marks this item as dirty on event.
        
        :param event: The event that marks the item as dirty.
        """
        self.dirty = True
    
    def refresh_content(self, event: Any = None):
        """
        Refreshes content on event.
        
        :param event: The event to refresh.
        """
        # if self.dirty:
        self._w = self._create_display_widget(event)
        # self.dirty = False
    
    def selectable(self):
        return True
    
    def keypress(self, size, key: str = '') -> str:
        if key in ['enter', ' ', 'up', 'down']:
            if self.application is not None:
                self._hidden_widget.keypress(size, key)
                self.application.handle_event(f'multimenuitem {key}')
                # self._hidden_widget.keypress(size, key)
                # self.refresh_content(key)
                self.redraw(key)
                # emit_signal(self, 'activate', key)
        else:
            if self.application is not None:
                if not key == 'esc':
                    # self.refresh_content(key)
                    self.application.handle_event(key)
            if key in ['tab']:
                return 'second tab'
            return key
    
    def mouse_event(self, *args, **kwargs):
        return self._hidden_widget.mouse_event(*args, **kwargs)
    
    def get_id(self):
        return self._id
    
    def get_column_content(self):
        return self._column_content
    
    def get_selected(self) -> MultiRadioButton:
        """
        Gives the selected item back.
        
        :return: The selected MultioRadioButton.
        """
        mrb: MultiRadioButton
        for mrb in self._group:
            if mrb.state:
                return mrb
        return None
    
    def get_selected_id(self) -> int:
        """
        Gives the selected id back (1+).

        :return: The selected id as int > 1.
        """
        return None if self.get_selected() is None else self.get_selected().get_id()
    
    def redraw(self, event: Any):
        """
        Redraws on event.

        :param event: The event to redraw.
        """
        if self.parent_listbox is not None:
            self.current_focus = self.parent_listbox.focus_position
            offset = 0
            if event in ['up', 'down']:
                offset += -1 if event == 'up' else 1
            new_pos: int = self.current_focus + offset
            if new_pos < 0:
                new_pos = 0
            elif new_pos > len(self._group) - 1:
                new_pos = len(self._group) - 1
            self.last_focus = self.current_focus
            self.current_focus = new_pos
            # self._group[self.last_focus].parent.refresh_content(event)
            self.refresh_content(event)
            # self._group[self.current_focus].parent.refresh_content(event)
            # self._group[0].parent.refresh_content(event)
    
    def redraw_triggered(self, event):
        """
        Redraws on event. Method triggers all groups MultiRadioButtons trigger_multi_menu_item_redraw methods.

        :param event: The event to redraw.
        """
        mrb: MultiRadioButton
        group_clone = self._group
        self._group = []
        for mrb in group_clone:
            mrb.trigger_multi_menu_item_redraw(event)
    
    def set_parent_listbox(self, parent: ListBox):
        """
        Sets the parent ListBox containing this item.
        
        :param parent: Parent ListBox
        """
        self.parent_listbox = parent
        userdata: Dict = {'parent_listbox_focus': (lambda: self.parent_listbox.focus_position)}
        connect_signal(self.parent_listbox.body, 'modified', self.handle_modified, user_args=[self.parent_listbox.body,
                                                                                              userdata])
    
    def render(self, size: Any, focus: bool = False) -> CompositeCanvas:
        """
        Renders the widget.
        
        :param size: Size of cols and/or rows.
        :param focus: True if item has focus.
        """
        return super(MultiMenuItem, self).render(size, focus)
    
    def handle_modified(self, walker: ListWalker = None, *args, **kwargs):
        """
        Is called if item is modified (changes state).
        
        :param walker: The first element of user_args (user_args=[walker, *args,, **kwargs]
        :param args: Optional user_args.
        :param kwargs: Optional keyword args
        """
        focus: int = args[0]['parent_listbox_focus']()
        if self.application is not None:
            self.application.print(f"MultiMenuItem({self._id}).handle_modified() *args({args}) **kwargs({kwargs})")
            self.redraw(f'modified multi menu item focus on {focus} enter')
    
    def handle_changed(self, *args, **kwargs):
        """
        Is called if item is chnaged (???).
        TODO Check what this does exactly.  or when it is called

        :param args: Optional user_args.
        :param kwargs: Optional keyword args
        """
        if self.application is not None:
            self.application.print(f"Called MultiMenuItem({self._id}).handle_changed() with args({args}) und "
                                   f"kwargs({kwargs})")
    
    def set_focus(self):
        """
        Sets focus to this item.
        """
        if self.parent_listbox is not None:
            self.parent_listbox.body.set_focus(self._id - 1)
    
    def set_state(self, state):
        """
        Toggles state at this item to state.
        
        :param state: Set toggle to on if True, off otherwise.
        """
        self._state = state
    
    @classmethod
    def handle_menu_changed(cls, item: WidgetDrawer, state: bool, *args, **kwargs):
        """
        Is called additionally if item is chnaged (???).
        TODO Check what this does exactly.  or when it is called
        
        :param item: The calling MWidget.
        :param state: The new state.
        :param args: Optional user_args.
        :param kwargs: Optional keyword args
        """
        mrb: MultiRadioButton = item
        mmi: MultiMenuItem = mrb.parent
        # mmi.set_state(state)
        # schau mer mal
        if cls.application is not None:
            cls.application.print(
                f"Called item._id of MultiMenuItem({mrb.get_id()}).handle_menu_changed(item={item}, state={state}) with"
                f" args({args}) und kwargs({kwargs})")
            if state:
                cls.application.maybe_menu_state = mrb.get_id()


class MenuItemError(Exception):
    pass


def multi_menu_item(group, id, label, column_content, state, on_state_change, user_data, application) -> MultiMenuItem:
    return MultiMenuItem(group, id, label, column_content, state, on_state_change, user_data, application)
