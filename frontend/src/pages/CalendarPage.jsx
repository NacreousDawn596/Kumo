import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addDays,
  addMonths,
  addWeeks,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  isToday,
  startOfMonth,
  startOfWeek,
  subMonths,
  subWeeks,
} from "date-fns";
import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { api, apiPost } from "../api/client.js";
import { Button, Dialog, Input } from "../components/ui.jsx";
import "../styles/pages.css";
import "./calendar.css";

const VIEWS = [
  { id: "month", label: "Month" },
  { id: "week", label: "Week" },
  { id: "day", label: "Day" },
  { id: "agenda", label: "Agenda" },
];

export default function CalendarPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState("month");
  const [month, setMonth] = useState(startOfMonth(new Date()));
  const [weekStart, setWeekStart] = useState(startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [day, setDay] = useState(new Date());
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [startAt, setStartAt] = useState(format(new Date(), "yyyy-MM-dd'T'HH:mm"));

  const monthRangeStart = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
  const monthRangeEnd = endOfMonth(month);
  const weekDays = eachDayOfInterval({ start: weekStart, end: endOfWeek(weekStart, { weekStartsOn: 1 }) });

  const { data: events = [] } = useQuery({
    queryKey: ["events", format(month, "yyyy-MM")],
    queryFn: () =>
      api(
        `/api/calendar?start=${format(monthRangeStart, "yyyy-MM-dd")}T00:00:00Z&end=${format(addMonths(monthRangeEnd, 1), "yyyy-MM-dd")}T00:00:00Z`
      ),
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ["tasks"],
    queryFn: () => api("/api/tasks"),
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

  const label = view === "month" ? format(month, "MMMM yyyy")
    : view === "week" ? `${format(weekStart, "MMM d")} – ${format(endOfWeek(weekStart, { weekStartsOn: 1 }), "MMM d, yyyy")}`
    : view === "day" ? format(day, "EEEE, MMMM d")
    : "Agenda";

  const prev = () => {
    if (view === "month") setMonth(subMonths(month, 1));
    else if (view === "week") setWeekStart(subWeeks(weekStart, 1));
    else if (view === "day") setDay(addDays(day, -1));
  };
  const next = () => {
    if (view === "month") setMonth(addMonths(month, 1));
    else if (view === "week") setWeekStart(addWeeks(weekStart, 1));
    else if (view === "day") setDay(addDays(day, 1));
  };

  const eventsOn = (d) => events.filter((e) => isSameDay(new Date(e.start_at), d));
  const tasksOn = (d) => tasks.filter((t) => t.due_date && t.status !== "done" && isSameDay(new Date(t.due_date), d));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">{label}</h1>
        </div>
        <div className="page-actions">
          <div className="view-switcher">
            {VIEWS.map((v) => (
              <button key={v.id} className={`view-chip ${view === v.id ? "view-chip-active" : ""}`} onClick={() => setView(v.id)}>
                {v.label}
              </button>
            ))}
          </div>
          <Button variant="ghost" icon={ChevronLeft} onClick={prev} />
          <Button variant="ghost" onClick={() => { setMonth(startOfMonth(new Date())); setWeekStart(startOfWeek(new Date(), { weekStartsOn: 1 })); setDay(new Date()); }}>Today</Button>
          <Button variant="ghost" icon={ChevronRight} onClick={next} />
          <Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Event</Button>
        </div>
      </div>

      {view === "month" && (
        <MonthView month={month} eventsOn={eventsOn} tasksOn={tasksOn} />
      )}

      {view === "week" && (
        <WeekView days={weekDays} eventsOn={eventsOn} tasksOn={tasksOn} />
      )}

      {view === "day" && (
        <DayView day={day} eventsOn={eventsOn} tasksOn={tasksOn} />
      )}

      {view === "agenda" && (
        <AgendaView events={events} tasks={tasks} />
      )}

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

function MonthView({ month, eventsOn, tasksOn }) {
  const days = eachDayOfInterval({ start: startOfWeek(startOfMonth(month), { weekStartsOn: 1 }), end: endOfMonth(month) });
  return (
    <>
      <div className="cal-weekdays">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="cal-weekday">{d}</div>)}
      </div>
      <div className="cal-grid">
        {days.map((d) => {
          const evs = eventsOn(d);
          const ts = tasksOn(d);
          return (
            <div key={d.toISOString()} className={`cal-day ${!isSameMonth(d, month) ? "cal-day-outside" : ""} ${isToday(d) ? "cal-day-today" : ""}`}>
              <span className="cal-day-num">{format(d, "d")}</span>
              <div className="cal-events">
                {evs.slice(0, 3).map((e) => <div key={e.id} className="cal-event" title={e.title}>{e.title}</div>)}
                {ts.map((t) => <div key={t.id} className="cal-task" title={`Task: ${t.title}`}>{t.title}</div>)}
                {evs.length > 3 && <div className="cal-more">+{evs.length - 3}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function WeekView({ days, eventsOn, tasksOn }) {
  return (
    <div className="cal-week">
      {days.map((d) => (
        <div key={d.toISOString()} className={`cal-week-col ${isToday(d) ? "cal-day-today" : ""}`}>
          <div className="cal-week-head">
            <span className="cal-week-dayname">{format(d, "EEE")}</span>
            <span className="cal-week-num">{format(d, "d")}</span>
          </div>
          <div className="cal-events">
            {eventsOn(d).map((e) => (
              <div key={e.id} className="cal-event" title={e.title}>
                {format(new Date(e.start_at), "h:mm")} {e.title}
              </div>
            ))}
            {tasksOn(d).map((t) => (
              <div key={t.id} className="cal-task" title={`Task: ${t.title}`}>{t.title}</div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function DayView({ day, eventsOn, tasksOn }) {
  const evs = eventsOn(day);
  const ts = tasksOn(day);
  return (
    <div className="cal-day-view">
      {evs.length === 0 && ts.length === 0 ? (
        <p className="home-muted">Nothing scheduled.</p>
      ) : (
        <div className="cal-day-list">
          {[...evs.map((e) => ({ id: e.id, title: e.title, time: format(new Date(e.start_at), "h:mm a"), type: "event" })),
            ...ts.map((t) => ({ id: t.id, title: t.title, time: "Task", type: "task" }))].map((item) => (
            <div key={`${item.type}-${item.id}`} className="card-row">
              <span className="cal-day-time">{item.time}</span>
              <span className="note-title">{item.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AgendaView({ events, tasks }) {
  const items = [
    ...events.map((e) => ({ id: e.id, title: e.title, date: new Date(e.start_at), type: "event" })),
    ...tasks.filter((t) => t.due_date && t.status !== "done").map((t) => ({ id: t.id, title: t.title, date: new Date(t.due_date), type: "task" })),
  ].sort((a, b) => a.date - b.date);

  if (items.length === 0) return <p className="home-muted">Nothing upcoming.</p>;

  return (
    <div className="card">
      {items.map((item) => (
        <div key={`${item.type}-${item.id}`} className="card-row">
          <span className="cal-day-time">{format(item.date, "MMM d")}</span>
          <span className="note-title">{item.title}</span>
          <span className="search-result-type">{item.type}</span>
        </div>
      ))}
    </div>
  );
}
