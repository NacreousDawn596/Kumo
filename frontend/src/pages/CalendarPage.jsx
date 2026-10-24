import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, Input, Textarea } from "../components/ui.jsx";
import "../styles/pages.css";
import "./calendar.css";

export default function CalendarPage() {
  const queryClient = useQueryClient();
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [startAt, setStartAt] = useState(format(new Date(), "yyyy-MM-dd'T'HH:mm"));

  const rangeStart = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
  const rangeEnd = endOfMonth(month);

  const { data: events = [] } = useQuery({
    queryKey: ["events", format(month, "yyyy-MM")],
    queryFn: () =>
      api(
        `/api/calendar?start=${format(rangeStart, "yyyy-MM-dd")}T00:00:00Z&end=${format(addMonths(rangeEnd, 1), "yyyy-MM-dd")}T00:00:00Z`
      ),
  });

  const create = useMutation({
    mutationFn: () =>
      apiPost("/api/calendar", {
        title: title || "Untitled event",
        start_at: new Date(startAt).toISOString(),
        all_day: false,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
      setCreating(false);
      setTitle("");
    },
  });

  const days = eachDayOfInterval({ start: rangeStart, end: rangeEnd });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">{format(month, "MMMM yyyy")}</h1>
        </div>
        <div className="page-actions">
          <Button variant="ghost" icon={ChevronLeft} onClick={() => setMonth(subMonths(month, 1))} />
          <Button variant="ghost" onClick={() => setMonth(new Date())}>Today</Button>
          <Button variant="ghost" icon={ChevronRight} onClick={() => setMonth(addMonths(month, 1))} />
          <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>
            Event
          </Button>
        </div>
      </div>

      <div className="cal-weekdays">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="cal-weekday">{d}</div>
        ))}
      </div>

      <div className="cal-grid">
        {days.map((day) => {
          const dayEvents = events.filter((e) => isSameDay(new Date(e.start_at), day));
          return (
            <div
              key={day.toISOString()}
              className={`cal-day ${!isSameMonth(day, month) ? "cal-day-outside" : ""} ${
                isToday(day) ? "cal-day-today" : ""
              }`}
            >
              <span className="cal-day-num">{format(day, "d")}</span>
              <div className="cal-events">
                {dayEvents.slice(0, 3).map((e) => (
                  <div key={e.id} className="cal-event" title={e.title}>
                    {e.title}
                  </div>
                ))}
                {dayEvents.length > 3 && <div className="cal-more">+{dayEvents.length - 3}</div>}
              </div>
            </div>
          );
        })}
      </div>

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New event"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>Create</Button>
          </>
        }
      >
        <div className="note-create">
          <Input autoFocus placeholder="Event title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} />
        </div>
      </Dialog>
    </div>
  );
}
