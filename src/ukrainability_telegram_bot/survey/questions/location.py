"""Location response handler."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import redacted_coordinate, safe_send_message, send_next_step_prompt
from .base import resolve_actions


@dataclass(frozen=True)
class LocationCallbacks:
    update_activity_timestamp: Callable[[int], Any]
    send_welcome: Callable[..., Any]
    ask_purpose_visit: Callable[[int, int, str], Any]
    location_handler: Callable[..., Any]


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> LocationCallbacks:
    actions = resolve_actions(ctx, actions)
    return LocationCallbacks(
        update_activity_timestamp=actions.update_activity_timestamp,
        send_welcome=actions.send_welcome,
        ask_purpose_visit=actions.ask_purpose_visit,
        location_handler=actions.handle_location_step,
    )


def handle_location_step(
    ctx: AppContext,
    message: Any,
    callbacks: LocationCallbacks,
) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id
    try:
        callbacks.update_activity_timestamp(user_id)

        language = ctx.sessions.get_data(user_id, "language")
        if not language:
            profile_language = ctx.sessions.get_profile(user_id, "language")
            if profile_language:
                language = profile_language
                ctx.sessions.set_data(user_id, "language", language)
            else:
                safe_send_message(ctx, chat_id, messages["en"]["please_use_start"])
                return

        remove_keyboard = types.ReplyKeyboardRemove()

        if message.content_type == "location":
            latitude = message.location.latitude
            longitude = message.location.longitude
            venue_title = ""
            venue_address = ""
            if hasattr(message, "venue") and message.venue:
                if hasattr(message.venue, "title") and message.venue.title:
                    venue_title = message.venue.title
                if hasattr(message.venue, "address") and message.venue.address:
                    venue_address = message.venue.address

            ctx.sessions.set_data(
                user_id,
                "location",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "venue_title": venue_title,
                    "venue_address": venue_address,
                },
            )
            ctx.flow_logger.info(
                "Coordinate location received - "
                f"lat~{redacted_coordinate(latitude)}, long~{redacted_coordinate(longitude)}"
            )
            if venue_title or venue_address:
                location_info = (
                    f"{venue_title}, {venue_address}"
                    if venue_title and venue_address
                    else venue_title or venue_address
                )
                location_received_msg = (
                    f"📍 {messages[language]['location_received']}: {location_info}"
                )
            else:
                location_received_msg = (
                    f"📍 {messages[language]['location_received']}: {latitude}, {longitude}"
                )
            safe_send_message(
                ctx,
                chat_id,
                location_received_msg,
                reply_markup=remove_keyboard,
            )
            callbacks.ask_purpose_visit(chat_id, user_id, language)
            return

        if message.content_type == "venue":
            latitude = message.venue.location.latitude
            longitude = message.venue.location.longitude
            venue_title = message.venue.title
            venue_address = message.venue.address
            ctx.sessions.set_data(
                user_id,
                "location",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "venue_title": venue_title,
                    "venue_address": venue_address,
                },
            )
            ctx.flow_logger.info("Venue location received; title/address redacted")
            safe_send_message(
                ctx,
                chat_id,
                f"📍 {messages[language]['location_received']}: {venue_title}, {venue_address}",
                reply_markup=remove_keyboard,
            )
            callbacks.ask_purpose_visit(chat_id, user_id, language)
            return

        if message.content_type == "text":
            location_text = message.text.strip()
            if location_text.startswith("/"):
                if location_text.startswith("/start"):
                    callbacks.send_welcome(message)
                    return
                send_next_step_prompt(
                    ctx,
                    chat_id,
                    messages[language]["please_send_location"],
                    callbacks.location_handler,
                )
                return

            ctx.flow_logger.info("Text location received; content redacted")
            ctx.sessions.set_data(
                user_id,
                "location",
                {
                    "latitude": "",
                    "longitude": "",
                    "venue_title": "",
                    "venue_address": location_text,
                },
            )
            ctx.flow_logger.info("Text location stored in session; content redacted")
            safe_send_message(
                ctx,
                chat_id,
                f"📍 {messages[language]['location_received']}: {location_text}",
                reply_markup=remove_keyboard,
            )
            callbacks.ask_purpose_visit(chat_id, user_id, language)
            return

        send_next_step_prompt(
            ctx,
            chat_id,
            messages[language]["please_send_location"],
            callbacks.location_handler,
        )
    except Exception as exc:
        logging.exception(f"Error in handle_location_step: {exc}")
        try:
            language = ctx.sessions.get_data(user_id, "language", "en")
            error_msg = messages[language].get(
                "error_occurred",
                messages["en"]["error_occurred"],
            )
            ctx.bot.reply_to(message, error_msg)
        except Exception:
            ctx.bot.reply_to(message, messages["en"]["error_occurred_bilingual"])
