"""Performance session UI; Tk updates stay on the main thread."""
import json
import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
from core.performance import PerformanceSession, bottlenecks, compare_reports


class PerformanceView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color='transparent')
        self.app, self.session, self.running, self.pending = app, None, False, False
        self.generation = 0
        self.timer = None
        actions = ctk.CTkFrame(self)
        actions.pack(fill='x',pady=8)
        for title, command in [('Start Session',self.start),('Stop',self.stop),('Save JSON',self.save),('Compare Sessions',self.compare)]:
            ctk.CTkButton(actions,text=title,command=command,width=140).pack(side='left',padx=5,pady=8)
        self.status = ctk.CTkLabel(self,text='Connect a TV. Sampling pauses for five seconds after each completed reading.',wraplength=800)
        self.status.pack(fill='x')
        self.metrics = ctk.CTkLabel(self,text='CPU — · RAM — · Swap — · Processes —',font=ctk.CTkFont(size=17))
        self.metrics.pack(fill='x',pady=8)
        self.chart = tk.Canvas(self,height=140,bg='#17181d',highlightthickness=0)
        self.chart.pack(fill='x')
        self.chart.bind('<Configure>',lambda _e:self.draw())
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill='both',expand=True,pady=8)
        self.table = ttk.Treeview(table_frame,columns=('pid','name','cpu','rss','pss'),show='headings',height=7)
        for key,title in [('pid','PID'),('name','Process'),('cpu','CPU %'),('rss','RSS KiB'),('pss','PSS KiB')]:
            self.table.heading(key,text=title,command=lambda k=key:self.show_processes(k))
            self.table.column(key,width=240 if key=='name' else 90)
        self.table.pack(side='left',fill='both',expand=True)
        bar = ttk.Scrollbar(table_frame,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y')
        self.details = ctk.CTkTextbox(self,height=140)
        self.details.pack(fill='both',expand=True)

    def start(self):
        if self.running or self.pending: return
        if not self.app.selected_serial:
            self.status.configure(text='No TV connected.')
            return
        self.generation += 1
        self.session = PerformanceSession(self.app.adb,self.app.selected_serial)
        self.running = True
        self.tick()

    def stop(self):
        self.running = False
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        self.status.configure(text='Session stopped. Any reading already in progress will be retained.')

    def tick(self):
        if not self.running or self.pending: return
        if self.app.selected_serial != self.session.serial:
            self.stop()
            return
        self.pending = True
        token = self.generation
        def done(sample):
            self.pending = False
            if token != self.generation: return
            ram = sample['ram']
            def val(x): return '—' if x is None else f'{x:,.1f}'
            utilization = 100*(1-ram['available_kb']/ram['total_kb']) if ram.get('total_kb') and ram.get('available_kb') is not None else None
            self.metrics.configure(text=f"CPU {val(sample['cpu']['overall_percent'])}% · RAM unavailable {val(utilization)}% · Swap {val(ram['swap_used_kb'])} KiB · Processes {val(sample['process_count'])}")
            self.status.configure(text=f"Samples: {len(self.session.samples)} · {sample['timestamp']} · Cached RAM is reclaimable; it is not wasted memory.")
            self.show_processes('rss')
            self.draw()
            self.details.delete('1.0','end')
            findings = bottlenecks(self.session.samples)
            self.details.insert('end',json.dumps({'RAM':ram,'cpu_window':sample['cpu']['window'],'findings':findings,'errors':sample['errors'],
                'service_observation':self.session.services},ensure_ascii=False,indent=2))
            if self.running: self.timer = self.after(5000,self.tick)
        def failed(error):
            self.pending = False
            self.running = False
            self.status.configure(text=f'Sampling stopped: {error}')
        self.app._background(self.session.sample,done,'Reading performance telemetry…',failure=failed)

    def show_processes(self,sort='rss'):
        if not self.session or not self.session.samples: return
        s = self.session.samples[-1]
        rows = {r['pid']:{**r} for r in s['processes']}
        for r in s['cpu']['processes']:
            rows.setdefault(r['pid'],{'pid':r['pid'],'name':r['name']}).update(cpu_percent=r['cpu_percent'])
        for r in s['pss'] or []:
            rows.setdefault(r['pid'],{'pid':r['pid'],'name':r['name']}).update(pss_kb=r['pss_kb'])
        key = {'cpu':'cpu_percent','rss':'rss_kb','pss':'pss_kb'}.get(sort,sort)
        data = sorted(rows.values(),key=lambda r:r.get(key) or ('' if key=='name' else -1),reverse=key!='name')
        self.table.delete(*self.table.get_children())
        for r in data: self.table.insert('','end',values=[r.get(k,'—') if r.get(k) is not None else '—' for k in ('pid','name','cpu_percent','rss_kb','pss_kb')])

    def draw(self):
        self.chart.delete('all')
        self.chart.create_text(10,12,anchor='w',fill='white',text='History: CPU % (blue) · available RAM % (green) · range 0–100')
        if not self.session: return
        samples = self.session.samples[-120:]
        width = max(self.chart.winfo_width()-30,1)
        for color, fn in [('#6aaaff',lambda s:s['cpu']['overall_percent']),('#75c9a0',lambda s:100*s['ram']['available_kb']/s['ram']['total_kb'] if s['ram'].get('total_kb') and s['ram'].get('available_kb') is not None else None)]:
            prev = None
            for i,s in enumerate(samples):
                value = fn(s)
                if value is None: prev=None; continue
                point = (15+i*width/max(len(samples)-1,1),125-min(100,max(0,value)))
                if prev: self.chart.create_line(*prev,*point,fill=color,width=2)
                self.chart.create_oval(point[0]-2,point[1]-2,point[0]+2,point[1]+2,fill=color,outline=color)
                prev=point

    def save(self):
        if not self.session: return
        path = filedialog.asksaveasfilename(defaultextension='.json',initialfile='yaos-performance.json')
        if path:
            try: self.session.save(path); self.status.configure(text=f'Saved: {path}')
            except OSError as exc: self.status.configure(text=str(exc))

    def compare(self):
        paths = filedialog.askopenfilenames(title='Select two session reports',filetypes=[('JSON','*.json')])
        if len(paths)!=2: return
        try:
            with open(paths[0],encoding='utf-8') as f: first=json.load(f)
            with open(paths[1],encoding='utf-8') as f: second=json.load(f)
            result=compare_reports(first,second)
            self.details.delete('1.0','end'); self.details.insert('end',json.dumps(result,ensure_ascii=False,indent=2))
        except (OSError,ValueError,KeyError,TypeError) as exc: self.status.configure(text=f'Could not compare: {exc}')
