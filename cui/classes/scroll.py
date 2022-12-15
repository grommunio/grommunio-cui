# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""This module contains Scrollable widgets"""
import urwid
from urwid.widget import BOX, FIXED, FLOW

# Scroll actions
SCROLL_LINE_UP = "line up"
SCROLL_LINE_DOWN = "line down"
SCROLL_PAGE_UP = "page up"
SCROLL_PAGE_DOWN = "page down"
SCROLL_TO_TOP = "to top"
SCROLL_TO_END = "to end"

# Scrollbar positions
SCROLLBAR_LEFT = "left"
SCROLLBAR_RIGHT = "right"


class Scrollable(urwid.WidgetDecoration):
    """The Scrollable class to create a urwid scrollable widget base."""
    def sizing(self):
        return frozenset(
            [
                BOX,
            ]
        )

    def selectable(self):
        return True

    def __init__(self, widget):
        """Box widget that makes a fixed or flow widget vertically scrollable
        TODO: Focusable widgets are handled, including switching focus, but
        possibly not intuitively, depending on the arrangement of widgets.  When
        switching focus to a widget that is outside of the visible part of the
        original widget, the canvas scrolls up/down to the focused widget.  It
        would be better to scroll until the next focusable widget is in sight
        first.  But for that to work we must somehow obtain a list of focusable
        rows in the original canvas.
        """
        if not any(s in widget.sizing() for s in (FIXED, FLOW)):
            raise ValueError(f"Not a fixed or flow widget: {widget}")
        self._trim_top = 0
        self._scroll_action = None
        self._forward_keypress = None
        self._old_cursor_coords = None
        self._rows_max_cached = 0
        super().__init__(widget)

    def render(self, size, focus=False):
        """
        Render wrapped widget and apply attribute. Return canvas.
        """
        def canv_pad_trim(cur_val, max_val, func):
            if cur_val <= max_val:
                diff = max_val - cur_val
                if diff > 0:
                    # Canvas is narrower than available horizontal space
                    func(0, diff)

        var = {"maxcol": size[0], "maxrow": size[1]}

        # Render complete original widget
        original_widget = self._original_widget
        var["ow_size"] = self._get_original_widget_size(size)
        var["canv_full"] = original_widget.render(var["ow_size"], focus)

        # Make full canvas editable
        canv = urwid.CompositeCanvas(var["canv_full"])
        canv_cols, canv_rows = canv.cols(), canv.rows()

        canv_pad_trim(canv_cols, var["maxcol"], canv.pad_trim_left_right)
        # if canv_cols <= var["maxcol"]:
        #     pad_width = var["maxcol"] - canv_cols
        #     if pad_width > 0:
        #         # Canvas is narrower than available horizontal space
        #         canv.pad_trim_left_right(0, pad_width)

        canv_pad_trim(canv_rows, var["maxrow"], canv.pad_trim_top_bottom)
        # if canv_rows <= var["maxrow"]:
        #     fill_height = var["maxrow"] - canv_rows
        #     if fill_height > 0:
        #         # Canvas is lower than available vertical space
        #         canv.pad_trim_top_bottom(0, fill_height)

        if canv_cols <= var["maxcol"] and canv_rows <= var["maxrow"]:
            # Canvas is small enough to fit without trimming
            return canv

        self._adjust_trim_top(canv, size)

        # Trim canvas if necessary
        trim_top = self._trim_top
        trim_end = canv_rows - var["maxrow"] - trim_top
        trim_right = canv_cols - var["maxcol"]
        if trim_top > 0:
            canv.trim(trim_top)
        if trim_end > 0:
            canv.trim_end(trim_end)
        if trim_right > 0:
            canv.pad_trim_left_right(0, -trim_right)

        # Disable cursor display if cursor is outside of visible canvas parts
        if canv.cursor is not None:
            _, cursrow = canv.cursor
            if cursrow >= var["maxrow"] or cursrow < 0:
                canv.cursor = None

        # Figure out whether we should forward keypresses to original widget
        if canv.cursor is not None:
            # Trimmed canvas contains the cursor, e.g. in an Edit widget
            self._forward_keypress = True
        elif var["canv_full"].cursor is not None:
            # Full canvas contains the cursor, but scrolled out of view
            self._forward_keypress = False
        else:
            # Original widget does not have a cursor, but may be selectable
            # pylint: disable=fixme
            # FIXME: Using original_widget.selectable() is bad because the original
            # widget may be selectable because it's a container widget with
            # a key-grabbing widget that is scrolled out of view.
            # original_widget.selectable() returns True anyway because it doesn't know
            # how we trimmed our canvas.
            #
            # To fix this, we need to resolve original_widget.focus and somehow
            # ask canv whether it contains bits of the focused widget.  I
            # can't see a way to do that.
            self._forward_keypress = original_widget.selectable()
        return canv

    def keypress(self, size, key):
        """Handle key event while event is NOT a mouse event in the
        form size, event"""
        # Maybe offer key to original widget
        if self._forward_keypress:
            original_widget = self._original_widget
            ow_size = self._get_original_widget_size(size)

            # Remember previous cursor position if possible
            if hasattr(original_widget, "get_cursor_coords"):
                self._old_cursor_coords = original_widget.get_cursor_coords(ow_size)

            key = original_widget.keypress(ow_size, key)
            if key is None:
                return None

        # Handle up/down, page up/down, etc
        command_map = self._command_map
        if command_map[key] == urwid.CURSOR_UP:
            self._scroll_action = SCROLL_LINE_UP
        elif command_map[key] == urwid.CURSOR_DOWN:
            self._scroll_action = SCROLL_LINE_DOWN

        elif command_map[key] == urwid.CURSOR_PAGE_UP:
            self._scroll_action = SCROLL_PAGE_UP
        elif command_map[key] == urwid.CURSOR_PAGE_DOWN:
            self._scroll_action = SCROLL_PAGE_DOWN

        elif command_map[key] == urwid.CURSOR_MAX_LEFT:  # 'home'
            self._scroll_action = SCROLL_TO_TOP
        elif command_map[key] == urwid.CURSOR_MAX_RIGHT:  # 'end'
            self._scroll_action = SCROLL_TO_END

        else:
            return key

        return self._invalidate()

    # pylint: disable=too-many-arguments
    # because mouse_event method on urwid is the same
    def mouse_event(self, size, event, button, col, row, focus):
        """Handle mouse event while event is a mouse event in the
        form size, event, button, col, row, focus"""
        original_widget = self._original_widget
        if hasattr(original_widget, "mouse_event"):
            ow_size = self._get_original_widget_size(size)
            row += self._trim_top
            return original_widget.mouse_event(ow_size, event, button, col, row, focus)
        return False

    def _adjust_trim_top(self, canv, size):
        """Adjust self._trim_top according to self._scroll_action"""
        action = self._scroll_action
        self._scroll_action = None

        var = {"maxcol": size[0], "maxrow": size[1]}
        trim_top = self._trim_top
        canv_rows = canv.rows()

        if trim_top < 0:
            # Negative trim_top values use bottom of canvas as reference
            trim_top = canv_rows - var["maxrow"] + trim_top + 1

        if canv_rows <= var["maxrow"]:
            self._trim_top = 0  # Reset scroll position
            return

        def ensure_bounds(new_trim_top):
            return max(0, min(canv_rows - var["maxrow"], new_trim_top))

        if action == SCROLL_LINE_UP:
            self._trim_top = ensure_bounds(trim_top - 1)
        elif action == SCROLL_LINE_DOWN:
            self._trim_top = ensure_bounds(trim_top + 1)

        elif action == SCROLL_PAGE_UP:
            self._trim_top = ensure_bounds(trim_top - var["maxrow"] + 1)
        elif action == SCROLL_PAGE_DOWN:
            self._trim_top = ensure_bounds(trim_top + var["maxrow"] - 1)

        elif action == SCROLL_TO_TOP:
            self._trim_top = 0
        elif action == SCROLL_TO_END:
            self._trim_top = canv_rows - var["maxrow"]

        else:
            self._trim_top = ensure_bounds(trim_top)

        # If the cursor was moved by the most recent keypress, adjust trim_top
        # so that the new cursor position is within the displayed canvas part.
        # But don't do this if the cursor is at the top/bottom edge so we can
        # still scroll out
        if (
            self._old_cursor_coords is not None
            and self._old_cursor_coords != canv.cursor
        ):
            self._old_cursor_coords = None
            _, cursrow = canv.cursor
            if cursrow < self._trim_top:
                self._trim_top = cursrow
            elif cursrow >= self._trim_top + var["maxrow"]:
                self._trim_top = max(0, cursrow - var["maxrow"] + 1)

    def _get_original_widget_size(self, size):
        original_widget = self._original_widget
        sizing = original_widget.sizing()
        if FIXED in sizing:
            return ()
        if FLOW in sizing:
            return (size[0],)
        return None

    def get_scrollpos(self, size=None, focus=False):
        """Current scrolling position
        Lower limit is 0, upper limit is the maximum number of rows with the
        given maxcol minus maxrow.
        NOTE: The returned value may be too low or too high if the position has
        changed but the widget wasn't rendered yet.
        """
        _ = size
        _ = focus
        return self._trim_top

    def set_scrollpos(self, position):
        """Set scrolling position
        If `position` is positive it is interpreted as lines from the top.
        If `position` is negative it is interpreted as lines from the bottom.
        Values that are too high or too low values are automatically adjusted
        during rendering.
        """
        self._trim_top = int(position)
        self._invalidate()

    def rows_max(self, size=None, focus=False):
        """Return the number of rows for `size`
        If `size` is not given, the currently rendered number of rows is returned.
        """
        if size is not None:
            original_widget = self._original_widget
            ow_size = self._get_original_widget_size(size)
            sizing = original_widget.sizing()
            if FIXED in sizing:
                self._rows_max_cached = original_widget.pack(ow_size, focus)[1]
            elif FLOW in sizing:
                self._rows_max_cached = original_widget.rows(ow_size, focus)
            else:
                raise RuntimeError(f"Not a flow/box widget: {self._original_widget}")
        return self._rows_max_cached


class ScrollBar(urwid.WidgetDecoration):
    """The ScrollBar class to create a urwid scrollbar."""
    def sizing(self):
        return frozenset((BOX,))

    def selectable(self):
        return True

    def __init__(
        self,
        widget,
        *args,
        **kwargs,
    ):
        """Box widget that adds a scrollbar to `widget`
        `widget` must be a box widget with the following methods:
          - `get_scrollpos` takes the arguments `size` and `focus` and returns
            the index of the first visible row.
          - `set_scrollpos` (optional; needed for mouse click support) takes the
            index of the first visible row.
          - `rows_max` takes `size` and `focus` and returns the total number of
            rows `widget` can render.
        `thumb_char` is the character used for the scrollbar handle.
        `trough_char` is used for the space above and below the handle.
        `side` must be 'left' or 'right'.
        `width` specifies the number of columns the scrollbar uses.
        """
        thumb_char = kwargs.get("thumb_char", args[0] if len(args) > 0 else "\u2588")
        trough_char = kwargs.get("trough_char", args[1] if len(args) > 1 else " ")
        side = kwargs.get("side", args[2] if len(args) > 2 else SCROLLBAR_RIGHT)
        width = kwargs.get("width", args[3] if len(args) > 3 else 1)
        if BOX not in widget.sizing():
            raise ValueError(f"Not a box widget: {widget}")
        super().__init__(widget)
        self._thumb_char = thumb_char
        self._trough_char = trough_char
        self.scrollbar_side = side
        self.scrollbar_width = max(1, width)
        self._original_widget_size = (0, 0)

    def render(self, size, focus=False):
        """
        Render wrapped widget and apply attribute. Return canvas.
        """
        var = {"maxcol": size[0], "maxrow": size[1], "sb_width": self._scrollbar_width}

        var["ow_size"] = (max(0, var["maxcol"] - var["sb_width"]), var["maxrow"])
        var["sb_width"] = var["maxcol"] - var["ow_size"][0]

        original_widget = self._original_widget
        var["ow_base"] = self.scrolling_base_widget
        var["ow_rows_max"] = var["ow_base"].rows_max(size, focus)
        if var["ow_rows_max"] <= var["maxrow"]:
            # Canvas fits without scrolling - no scrollbar needed
            self._original_widget_size = size
            return original_widget.render(size, focus)
        var["ow_rows_max"] = var["ow_base"].rows_max(var["ow_size"], focus)

        var["ow_canv"] = original_widget.render(var["ow_size"], focus)
        self._original_widget_size = var["ow_size"]

        pos = var["ow_base"].get_scrollpos(var["ow_size"], focus)
        posmax = var["ow_rows_max"] - var["maxrow"]

        # Thumb shrinks/grows according to the ratio of
        # <number of visible lines> / <number of total lines>
        var["thumb_weight"] = min(1, var["maxrow"] / max(1, var["ow_rows_max"]))
        var["thumb_height"] = max(1, round(var["thumb_weight"] * var["maxrow"]))

        # Thumb may only touch top/bottom if the first/last row is visible
        var["top_weight"] = float(pos) / max(1, posmax)
        var["top_height"] = int((var["maxrow"] - var["thumb_height"]) * var["top_weight"])
        if var["top_height"] == 0 and var["top_weight"] > 0:
            var["top_height"] = 1

        # Bottom part is remaining space
        bottom_height = var["maxrow"] - var["thumb_height"] - var["top_height"]
        assert var["thumb_height"] + var["top_height"] + bottom_height == var["maxrow"]

        # Create scrollbar canvas
        # Creating SolidCanvases of correct height may result in "cviews do not
        # fill gaps in shard_tail!" or "cviews overflow gaps in shard_tail!"
        # exceptions. Stacking the same SolidCanvas is a workaround.
        # https://github.com/urwid/urwid/issues/226#issuecomment-437176837
        top = urwid.SolidCanvas(self._trough_char, var["sb_width"], 1)
        thumb = urwid.SolidCanvas(self._thumb_char, var["sb_width"], 1)
        bottom = urwid.SolidCanvas(self._trough_char, var["sb_width"], 1)
        var["sb_canv"] = urwid.CanvasCombine(
            [(top, None, False)] * var["top_height"]
            + [(thumb, None, False)] * var["thumb_height"]
            + [(bottom, None, False)] * bottom_height,
        )

        combinelist = [
            (var["ow_canv"], None, True, var["ow_size"][0]),
            (var["sb_canv"], None, False, var["sb_width"]),
        ]
        if self._scrollbar_side != SCROLLBAR_LEFT:
            return urwid.CanvasJoin(combinelist)
        return urwid.CanvasJoin(reversed(combinelist))

    @property
    def scrollbar_width(self):
        """Columns the scrollbar uses"""
        return max(1, self._scrollbar_width)

    @scrollbar_width.setter
    def scrollbar_width(self, width):
        self._scrollbar_width = max(1, int(width))
        self._invalidate()

    @property
    def scrollbar_side(self):
        """Where to display the scrollbar; must be 'left' or 'right'"""
        return self._scrollbar_side

    @scrollbar_side.setter
    def scrollbar_side(self, side):
        if side not in (SCROLLBAR_LEFT, SCROLLBAR_RIGHT):
            raise ValueError(f'scrollbar_side must be "left" or "right", not {side}')
        self._scrollbar_side = side
        self._invalidate()

    @property
    def scrolling_base_widget(self):
        """Nearest `original_widget` that is compatible with the scrolling API"""

        def orig_iter(widget):
            while hasattr(widget, "original_widget"):
                widget = widget.original_widget
                yield widget
            yield widget

        def is_scrolling_widget(widget):
            return hasattr(widget, "get_scrollpos") and hasattr(widget, "rows_max")

        widget = None
        for widget in orig_iter(self):
            if is_scrolling_widget(widget):
                return widget
        raise ValueError(f"Not compatible to be wrapped by ScrollBar: {widget}")

    def keypress(self, _, key):
        """Handle key event while event is NOT a mouse event in the
        form size, event"""
        return self._original_widget.keypress(self._original_widget_size, key)

    # pylint: disable=too-many-arguments
    # because mouse_event method on urwid is the same
    def mouse_event(self, _, event, button, col, row, focus):
        """Handle mouse event while event is a mouse event in the
        form size, event, button, col, row, focus"""
        original_widget = self._original_widget
        ow_size = self._original_widget_size
        handled = False
        if hasattr(original_widget, "mouse_event"):
            handled = original_widget.mouse_event(ow_size, event, button, col, row, focus)

        if not handled and hasattr(original_widget, "set_scrollpos"):
            if button == 4:  # scroll wheel up
                pos = original_widget.get_scrollpos(ow_size)
                original_widget.set_scrollpos(pos - (1 if pos > 0 else 0))
                return True
            if button == 5:  # scroll wheel down
                pos = original_widget.get_scrollpos(ow_size)
                original_widget.set_scrollpos(pos + 1)
                return True

        return False
