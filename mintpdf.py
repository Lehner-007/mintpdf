#!/usr/bin/env python3
"""mintPDF GTK-4-Oberfläche, Josef Lehner, GPL-3.0-only.

Start: python3 mintpdf.py. Optional: --list-tools, --version, --tool ID
--input DATEI (wiederholbar), --output DATEI, --pages 1,3-5, --text TEXT.
Sprachdateien: UTF-8-JSON mit flachem Objekt aus Textschlüsseln und Strings.
Zusätzliche Sprachen und help/<code>.html werden dynamisch erkannt.
"""
from pathlib import Path
import argparse
import json
import logging
import os
import sys
import threading
import subprocess
import tempfile
import urllib.request
import re
from core import FUNCTIONS, FUNCTION_BY_ID, GROUPS, can_dispatch
from core import analyse_form, analyse_optimization, compare_documents, comparison_raster, comparison_report, COMPARISON_MODES, redact_regions

from core import VERSION, TOOLS, BY_ID, ZIP_TOOLS, available, process, split_groups, pdf_page_count, ocr_languages, missing_tools, dependency_report, pdf_security

BASE=Path(__file__).resolve().parent
STATE=BASE if os.access(BASE,os.W_OK) else Path.home()/'.local/share/mintpdf'
for directory in ('config','logs','languages','help'):
    try: (STATE/directory).mkdir(parents=True,exist_ok=True)
    except OSError as exc: print('E_FILE:',exc,file=sys.stderr)
def setup_logging():
    """Sitzungslog erhalten und Starts sichtbar trennen."""
    try:
        logging.basicConfig(filename=STATE/'logs/mintpdf.log',filemode='a',force=True,
                            level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    except OSError as exc:
        logging.basicConfig(level=logging.INFO,force=True)
        logging.error('E_LOG: %s',exc)
    logging.info('\n%s\nmintPDF %s gestartet\n%s','='*60,VERSION,'='*60)
    for name,functions,hint in dependency_report():
        logging.warning('E_DEP: %s fehlt; Funktionen: %s; Installationsvorschlag: %s',name,functions,hint)
    for module,command in [('gi','sudo apt install python3-gi gir1.2-gtk-4.0')]:
        try: __import__(module)
        except (ImportError,OSError): logging.warning('E_DEP: %s fehlt; Installationsvorschlag: %s',module,command)
    try:
        import gi
        gi.require_version('Gtk','4.0')
    except (ImportError,ValueError): logging.warning('E_DEP: GTK 4 fehlt; Installationsvorschlag: sudo apt install python3-gi gir1.2-gtk-4.0')



def read_json(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or any(not isinstance(v,str) for v in data.values()): raise ValueError('E_LANG')
    return data



def local_input_files(files, staging):
    """Resolve native selections; copy non-local Gio files without touching originals."""
    from gi.repository import Gio
    paths=[]
    for index,file in enumerate(files):
        path=file.get_path()
        if path is None:
            name=Path(file.get_basename() or 'input.pdf').name
            target=Path(staging)/f'{index}-{name}'
            file.copy(Gio.File.new_for_path(str(target)),Gio.FileCopyFlags.NONE,None,None,None)
            path=str(target)
        paths.append(path)
    return paths


def output_suggestion(tool,folder=None):
    """Downloads ist das Standardziel; vorhandene Dateinamen freihalten."""
    folder=Path(folder).expanduser() if folder else Path.home()/'Downloads'
    suffix='.txt' if tool=='text_extract' else '.zip' if tool in ZIP_TOOLS else '.pdf'
    candidate=folder/f'mintpdf-{tool}{suffix}'
    number=2
    while candidate.exists() or candidate.is_symlink():
        candidate=folder/f'mintpdf-{tool}-{number}{suffix}'
        number+=1
    return candidate


def select_save_target(parent,title,initial,selected,on_error,accept_label):
    """Ziel asynchron auswählen; ein Abbruch verändert das bisherige Ziel nicht."""
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gio,GLib
    destination=Path(initial).expanduser().absolute()
    folder=destination.parent
    while not folder.is_dir() and folder!=folder.parent:folder=folder.parent
    if not folder.is_dir():folder=Path.home()
    suffix=destination.suffix.lower() or '.pdf'
    title=title+' — '+suffix.lstrip('.').upper()
    file_filter=Gtk.FileFilter();file_filter.set_name(suffix.lstrip('.').upper())
    file_filter.add_pattern('*'+suffix)
    def accept(file):
        if not file:return
        path=file.get_path()
        if path is None:on_error(ValueError('E_INPUT'));return
        if not Path(path).suffix:path+=suffix
        selected(path)
    if hasattr(Gtk,'FileDialog'):
        picker=Gtk.FileDialog(title=title,modal=True)
        picker.set_accept_label(accept_label)
        picker.set_initial_folder(Gio.File.new_for_path(str(folder)))
        picker.set_initial_name(destination.name or 'mintpdf'+suffix)
        filters=Gio.ListStore.new(Gtk.FileFilter);filters.append(file_filter)
        picker.set_filters(filters);picker.set_default_filter(file_filter)
        picker._cancellable=Gio.Cancellable()
        def response(dialog,result):
            try:accept(dialog.save_finish(result))
            except GLib.Error as exc:
                cancelled=(exc.matches(Gtk.DialogError.quark(),Gtk.DialogError.DISMISSED) or
                           exc.matches(Gtk.DialogError.quark(),Gtk.DialogError.CANCELLED) or
                           exc.matches(Gio.io_error_quark(),Gio.IOErrorEnum.CANCELLED))
                if not cancelled:
                    logging.error('Zieldialog: %s',exc)
                    on_error(exc)
        picker.save(parent,picker._cancellable,response)
        return picker
    # Ältere GTK4-Versionen: Standardordner des Dialogs unverändert lassen.
    picker=Gtk.FileChooserNative(title=title,transient_for=parent,modal=True,action=Gtk.FileChooserAction.SAVE,accept_label=accept_label)
    picker.set_current_name(destination.name or 'mintpdf'+suffix);picker.add_filter(file_filter)
    def response(dialog,result):
        file=dialog.get_file() if result==Gtk.ResponseType.ACCEPT else None
        dialog.hide()
        GLib.idle_add(lambda:(dialog.destroy(),False)[1])
        accept(file)
    picker.connect('response',response);picker.show()
    return picker


def write_settings(settings):
    """Konfiguration atomar speichern, bestehende Einstellungen bei Fehler erhalten."""
    path=STATE/'config/settings.json'
    fd,temporary=tempfile.mkstemp(prefix='.settings-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(settings,stream,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally: Path(temporary).unlink(missing_ok=True)


def validate_output_folder(value):
    """Nur vorhandene, tatsächlich beschreibbare Ausgabeordner übernehmen."""
    try:
        if not value.strip(): raise ValueError()
        path=Path(value).expanduser()
        if not path.is_absolute() or not path.is_dir(): raise ValueError()
        with tempfile.TemporaryFile(dir=path) as probe: probe.write(b'mintPDF')
        return str(path.resolve())
    except (OSError,ValueError) as exc: raise ValueError('E_OUTPUT_DIR') from exc


def open_document_information(app, source):
    from gi.repository import Gtk,GLib
    from core import document_information
    dialog=Gtk.Window(title=app.tr('document_info'),transient_for=app.window,modal=True,default_width=660,default_height=600)
    box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=16,margin_end=16,margin_top=16,margin_bottom=16)
    dialog.set_child(box)
    heading=Gtk.Box(spacing=12);heading.append(app.icon('document_info',48));heading.append(Gtk.Label(label=app.tr('document_info'),xalign=0));box.append(heading)
    scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
    grid=Gtk.Grid(column_spacing=18,row_spacing=8);scroll.set_child(grid);box.append(scroll)
    status=Gtk.Label(label=app.tr('working'),wrap=True,xalign=0);box.append(status)
    close=Gtk.Button(label=app.tr('close'),halign=Gtk.Align.END);close.connect('clicked',lambda *_:dialog.close());box.append(close)
    alive=[True]
    def closing(*_):alive[0]=False;return False
    dialog.connect('close-request',closing)
    app.busy=True;app.apply_function_states(app.function_states)
    def work():
        try:data=document_information(source);error=None
        except Exception as exc:data=None;error=exc
        def finish():
            app.busy=False;app.apply_function_states(app.function_states)
            if not alive[0]:return False
            if error:
                dialog.destroy();app.error(error);return False
            dialog.document_data=data
            for row,(key,value) in enumerate(data.items()):
                if key=='page_sizes':value='\n'.join(f"{item['width']:g} × {item['height']:g} mm · {item['rotation']}° · {item['count']}" for item in value)
                elif key=='encrypted':value=app.tr('doc_yes' if value else 'doc_no')
                elif key=='size':value=f'{value:,} Bytes'.replace(',',' ')
                label=Gtk.Label(label=app.tr('doc_'+key),xalign=0,valign=Gtk.Align.START)
                text=Gtk.Label(label=str(value) if value!='' else '—',xalign=0,wrap=True,selectable=True,hexpand=True,max_width_chars=65)
                grid.attach(label,0,row,1,1);grid.attach(text,1,row,1,1)
            status.set_text(app.tr('doc_note'))
            return False
        GLib.idle_add(finish)
    threading.Thread(target=work,daemon=True).start();dialog.present();return dialog


def main():
    setup_logging()
    parser=argparse.ArgumentParser(description='mintPDF – PDF tools')
    parser.add_argument('--version',action='version',version=VERSION)
    parser.add_argument('--list-tools',action='store_true')
    parser.add_argument('--tool',choices=BY_ID)
    parser.add_argument('--input',action='append',default=[])
    parser.add_argument('--output')
    parser.add_argument('--pages',default='')
    parser.add_argument('--text',default='')
    parser.add_argument('--angle',default='90')
    parser.add_argument('--split-mode',choices=('single','chunks','cuts','ranges'),default='single')
    parser.add_argument('--split-size',default='2')
    parser.add_argument('--split-cuts',default='')
    parser.add_argument('--split-ranges',default='')
    parser.add_argument('--gs-profile',choices=('screen','ebook','printer','prepress','default'),default='ebook')
    parser.add_argument('--ocr-language',default='eng')
    parser.add_argument('--ocr-mode',choices=('skip','redo'),default='skip')
    parser.add_argument('--ocr-output',choices=('pdf','pdfa'),default='pdf')
    parser.add_argument('--ocr-optimize',choices=('0','1','2','3'),default='1')
    parser.add_argument('--ocr-rotate',action='store_true')
    parser.add_argument('--ocr-deskew',action='store_true')
    parser.add_argument('--image-dpi',choices=('72','144','150','300'),default='144')
    parser.add_argument('--opt-structure',choices=('0','1','3','4'),default='4')
    for name in ('opt-compress','opt-images','opt-font-compress'):
        parser.add_argument('--'+name,action=argparse.BooleanOptionalAction,default=True)
    for name in ('opt-fonts','opt-metadata','opt-attachments'):
        parser.add_argument('--'+name,action='store_true')
    args=parser.parse_args()
    if args.list_tools:
        for t in TOOLS: print(f'{t[0]:16} {"OK" if available(t[0]) else "MISSING":8} {t[3]}')
        return 0
    if args.tool:
        try:
            if not args.output and BY_ID[args.tool][5] not in ('external','check'): parser.error('--output is required')
            opts=vars(args)
            if BY_ID[args.tool][5]=='password' and (args.tool!='decrypt' or pdf_security(args.input[0])['locked']):
                import getpass
                opts['password']=getpass.getpass('Password: ')
            result=process(args.tool,args.input,args.output,opts)
            if args.tool=='pdfa_check':print(result+' — veraPDF: compliant')
            elif args.tool=='document_info':print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        except Exception as exc:
            print(f'{exc} — check inputs, tools and output path.',file=sys.stderr)
            return 1
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk, Gio, GLib, Gdk, GdkPixbuf, Pango

    class App(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='eu.dogtruck.mintpdf')
            self.config={}
            self.busy=False
            self.langs={}
            self.errors=[]
            try:
                p=STATE/'config/settings.json'
                if p.exists():
                    self.config=json.loads(p.read_text())
                    if not isinstance(self.config,dict): raise ValueError('E_CONFIG')
                    value=self.config.get('output_dir')
                    if 'output_dir' in self.config and (not isinstance(value,str) or not Path(value).is_absolute()):
                        self.config.pop('output_dir',None); self.errors.append('E_CONFIG')
            except Exception:
                self.config={}; self.errors.append('E_CONFIG'); logging.error('E_CONFIG settings.json')
            self.language=self.config.get('language','de')
            self.scan_languages()

        def scan_languages(self):
            found={}
            for root in dict.fromkeys((BASE,STATE)):
                for path in sorted((root/'languages').glob('*.json')):
                    try: found[path.stem]=read_json(path)
                    except Exception:
                        logging.error('E_LANG %s',path); self.errors.append('E_LANG')
            self.langs=found
            if len(found)==1: self.language=next(iter(found))
            elif self.language not in found: self.language='de' if 'de' in found else 'en'

        def tr(self,key):
            return self.langs.get(self.language,{}).get(key,self.langs.get('en',{}).get(key,key))

        def do_activate(self):
            self.window=Gtk.ApplicationWindow(application=self,title=f'mintPDF {VERSION}')
            self.window.set_default_size(1600,850)
            Gtk.Window.set_default_icon_name('mintpdf')
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(BASE/'resources/icons'))
            css=Gtk.CssProvider()
            css.load_from_data(b'.tool-tile { padding: 12px; font-weight: normal; }')
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.build()
            self.window.connect('close-request',self.close_requested)
            self.window.present()
            GLib.timeout_add_seconds(5,self.check_tools)
            if self.errors: self.message('E_FILE',', '.join(sorted(set(self.errors))))

        def close_requested(self,*unused):
            if self.busy:
                self.message('busy',self.tr('wait')); return True
            return False

        def action(self,name,callback):
            old=self.lookup_action(name)
            if old: self.remove_action(name)
            a=Gio.SimpleAction.new(name,None)
            a.connect('activate',lambda *_:callback())
            self.add_action(a)
            return a

        def build(self):
            self.scan_languages()
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
            self.window.set_child(root)
            menus=Gio.Menu()
            bar=Gtk.PopoverMenuBar.new_from_model(menus)
            root.append(bar)
            self.tool_menu=Gio.Menu()
            self.tiles={}
            self.function_states={f.id:(False,'checking','') for f in FUNCTIONS}
            self._checking=False
            self._home_generation=getattr(self,'_home_generation',0)+1
            self._tool_actions={}
            self._render_signature=None
            self.main_menu=menus
            self.file_menu=Gio.Menu()
            file_actions=Gio.Menu()
            for key,callback in [('workflow',self.workflow)]:
                file_actions.append(self.tr(key),'app.'+key)
                self.action(key,callback)
            self.file_menu.append_section(None,file_actions)
            preferences=Gio.Menu();preferences.append(self.tr('settings'),'app.settings')
            self.action('settings',self.settings)
            self.file_menu.append_section(None,preferences)
            file_exit=Gio.Menu();file_exit.append(self.tr('quit'),'app.quit')
            self.action('quit',lambda:self.window.close())
            self.file_menu.append_section(None,file_exit)
            menus.append_submenu(self.tr('file'),self.file_menu)
            menus.append_submenu(self.tr('tools'),self.tool_menu)
            help_menu=Gio.Menu()
            for key,callback in [('help',self.help),('show_logs',self.show_logs),('info',self.info),('about',self.about)]:
                entry=Gio.MenuItem.new(self.tr(key),'app.'+key)
                if key=='info':entry.set_icon(Gio.ThemedIcon.new('dialog-information-symbolic'))
                help_menu.append_item(entry)
                self.action(key,callback)
            menus.append_submenu(self.tr('help_menu'),help_menu)
            self.set_accels_for_action('app.help',['F1'])
            self.set_accels_for_action('app.quit',['<Primary>q'])
            for function in FUNCTIONS:
                self._tool_actions[function.id]=self.action(function.id,lambda k=function.id:self.tool_dialog(k))
            self.menu_bar=bar
            bar.connect('map',lambda *_:compact_menus(bar))
            heading=Gtk.Label(label='mintPDF Tools',xalign=0.5,margin_start=18,margin_end=18,margin_top=8)
            attributes=Pango.AttrList();attributes.insert(Pango.attr_scale_new(1.4));heading.set_attributes(attributes)
            root.append(heading)
            root.append(Gtk.Label(label=self.tr('tools_tagline'),xalign=0.5,wrap=True,margin_start=18,margin_end=18))
            search_label=Gtk.Label(label=self.tr('search_label'),xalign=0.5,wrap=True,margin_start=18,margin_end=18)
            root.append(search_label)
            search=Gtk.SearchEntry(placeholder_text=self.tr('search_functions'))
            search.set_hexpand(True)
            search.update_property([Gtk.AccessibleProperty.LABEL],[self.tr('search_functions')])
            search.connect('changed',lambda *_:self.filter_functions(search.get_text()))
            search_row=Gtk.Grid(column_homogeneous=True,margin_start=18,margin_end=18)
            search_row.attach(Gtk.Label(hexpand=True),0,0,1,1)
            search_row.attach(search,1,0,2,1)
            search_row.attach(Gtk.Label(hexpand=True),3,0,1,1)
            root.append(search_row); self.search=search
            self.set_accels_for_action('app.focus_search',['<Primary>f'])
            self.action('focus_search',lambda:search.grab_focus())
            scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
            groups=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18)
            for prop in ('margin_start','margin_end','margin_top','margin_bottom'): getattr(groups,'set_'+prop)(18)
            self.group_widgets={}
            self.tile_size_group=Gtk.SizeGroup(mode=Gtk.SizeGroupMode.BOTH)
            flow=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,min_children_per_line=1,max_children_per_line=8,column_spacing=10,row_spacing=10,homogeneous=True)
            groups.append(flow);self.tool_flow=flow
            for function in FUNCTIONS:
                key=function.id
                tile=Gtk.Button(); tile.add_css_class('tool-tile')
                content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
                image=self.icon(function.icon,64)
                content.append(image)
                label=Gtk.Label(label=self.tr(key),wrap=True,justify=Gtk.Justification.CENTER)
                label.set_max_width_chars(22);label.set_lines(2);label.set_ellipsize(Pango.EllipsizeMode.END); content.append(label)
                tile.set_child(content); tile.set_size_request(190,140);tile.set_halign(Gtk.Align.CENTER);tile.set_valign(Gtk.Align.START);self.tile_size_group.add_widget(tile)
                tile.update_property([Gtk.AccessibleProperty.LABEL],[self.tr(key)])
                tile.connect('clicked',lambda _,k=key:self.tool_dialog(k))
                card=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4)
                card.append(tile)
                reason=Gtk.Label(wrap=True,justify=Gtk.Justification.CENTER)
                reason.set_max_width_chars(22); card.append(reason)
                flow.append(card)
                self.tiles[key]=(card.get_parent(),tile,reason)
            self.empty_search=Gtk.Label(label=self.tr('no_functions'),wrap=True)
            groups.append(self.empty_search); scroll.set_child(groups)
            self.home_overlay=Gtk.Overlay();self.home_overlay.set_child(scroll)
            self.home_watermark=Gtk.Picture.new_for_filename(str(BASE/'assets/report_watermark.png'))
            self.home_watermark.set_opacity(0.10);self.home_watermark.set_can_target(False)
            self.home_watermark.set_can_focus(False);self.home_watermark.set_size_request(360,360)
            self.home_watermark.set_halign(Gtk.Align.CENTER);self.home_watermark.set_valign(Gtk.Align.CENTER)
            self.home_watermark.set_can_shrink(True)
            self.home_overlay.add_overlay(self.home_watermark);root.append(self.home_overlay)
            self.status=Gtk.Label(margin_bottom=12,wrap=True);root.append(self.status)
            self.apply_function_states(self.function_states)
            self.check_tools()

        def icon(self,name,size):
            path=next((BASE/'resources'/f'{name}.{ext}' for ext in ('png','svg') if (BASE/'resources'/f'{name}.{ext}').is_file()),None)
            image=Gtk.Image.new_from_file(str(path)) if path else Gtk.Image.new_from_icon_name('application-pdf')
            image.set_pixel_size(size)
            return image

        def filter_functions(self,query):
            visible=set()
            for function in FUNCTIONS:
                matches=function.matches(query,self.tr)
                self.tiles[function.id][0].set_visible(matches)
                if matches: visible.add(function.group)
            self.empty_search.set_visible(not visible)

        def apply_function_states(self,states):
            signature=(tuple(states.items()),self.busy)
            if signature==self._render_signature:return
            self._render_signature=signature
            self.function_states=states
            self.tool_menu.remove_all()
            count=0
            for group in GROUPS:
                model=Gio.Menu()
                for function in (f for f in FUNCTIONS if f.group==group):
                    key=function.id
                    yes,reason,detail=states[key]
                    enabled=yes and not self.busy
                    if self.busy: reason,detail='processing',''
                    explanation=self.tr(reason) if reason else self.tr('description_'+key)
                    if detail: explanation+=': '+detail
                    _,tile,note=self.tiles[key]
                    tile.set_sensitive(enabled);note.set_text(explanation)
                    note.set_visible(bool(reason))
                    tile.set_tooltip_text(self.tr('description_'+key))
                    tile.update_property([Gtk.AccessibleProperty.DESCRIPTION],[explanation])
                    self._tool_actions[key].set_enabled(enabled)
                    model.append(self.tr(key),'app.'+key)
                    count+=int(enabled)
                self.tool_menu.append_submenu(self.tr('group_'+group),model)
            for key in ('workflow','settings','default_output'):
                action=self.lookup_action(key)
                if action:action.set_enabled(not self.busy)
            self.status.set_text(self.tr('available').format(count=count,total=len(FUNCTIONS)))
            self.filter_functions(self.search.get_text())
            compact_menus(self.menu_bar)

        def check_tools(self):
            if self._checking:return True
            self._checking=True
            generation=self._home_generation
            def worker():
                states={f.id:f.status() for f in FUNCTIONS}
                def finish():
                    if generation==self._home_generation:
                        self._checking=False
                        self.apply_function_states(states)
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
            return True

        def message(self,title,text):
            dlg=Gtk.MessageDialog(transient_for=self.window,modal=True,text=self.tr(title),secondary_text=text,buttons=Gtk.ButtonsType.OK)
            dlg.connect('response',lambda d,*_:d.destroy()); dlg.present()

        def error(self,exc):
            code='E_EXISTS' if isinstance(exc,FileExistsError) else str(exc) if str(exc).startswith('E_') else 'E_FILE'
            logging.error('%s (%s)',code,type(exc).__name__)
            self.message(code,self.tr(code))

        def choose_files(self,parent=None,on_selected=None,tool='merge',selection_title=None):
            """Gemeinsamer Einstieg aller Dateiwerkzeuge mit passendem Filter."""
            request_key=('choose_html' if tool=='web' else 'choose_images' if tool=='images_pdf' else 'choose_two_pdf' if BY_ID[tool][4]=='two' else 'choose_pdfs' if BY_ID[tool][4]=='many' else 'choose_pdf')
            picker=Gtk.FileChooserNative(title=selection_title or self.tr(request_key),transient_for=parent or self.window,modal=True,action=Gtk.FileChooserAction.OPEN,accept_label=self.tr('open'),cancel_label=self.tr('cancel'))
            picker.set_select_multiple(BY_ID[tool][4] in ('many','two'))
            pdf_filter=Gtk.FileFilter()
            if tool=='web':
                pdf_filter.set_name('HTML');pdf_filter.add_mime_type('text/html');extensions=('html','htm')
            elif tool=='images_pdf':
                pdf_filter.set_name(self.tr('image_files'))
                extensions=('png','jpg','jpeg','tif','tiff','bmp','jp2')

            else:
                pdf_filter.set_name(self.tr('pdf_files'));pdf_filter.add_mime_type('application/pdf')
                extensions=('pdf',)
            for extension in extensions:
                pdf_filter.add_pattern('*.'+extension);pdf_filter.add_pattern('*.'+extension.upper())
            picker.add_filter(pdf_filter)
            self._file_picker=picker
            def response(p,result):
                files=p.get_files() if result==Gtk.ResponseType.ACCEPT else None
                chosen=[files.get_item(i) for i in range(files.get_n_items())] if files else []
                p.hide();p.destroy();self._file_picker=None
                def dispatch(selected):
                    if not selected:return False
                    if BY_ID[tool][4]=='two' and len(selected)!=2:
                        self.message('choose',self.tr('choose_two'));return False
                    if on_selected:on_selected(selected)
                    else:self.tool_dialog(tool,selected)
                    return False
                if not chosen:return
                if all(file.get_path() is not None for file in chosen):
                    GLib.idle_add(dispatch,[file.get_path() for file in chosen]);return
                # Gio can return network/document-portal URIs without a local path.
                # Keep staged copies for this application session, including workers.
                staging=BASE/'work';staging.mkdir(exist_ok=True)
                temporary=tempfile.TemporaryDirectory(prefix='selected-input-',dir=staging)
                if not hasattr(self,'_input_staging'):
                    self._input_staging=[]
                    self.connect('shutdown',lambda *_:[item.cleanup() for item in self._input_staging])
                self._input_staging.append(temporary)
                self.busy=True;self.apply_function_states(self.function_states)
                def copy_inputs():
                    try:
                        selected=local_input_files(chosen,temporary.name);failure=None
                    except Exception as exc:
                        selected=[];failure=exc
                        logging.exception('Dateiauswahl %s: Arbeitskopie nicht lesbar',tool)
                    def finish():
                        self.busy=False;self.apply_function_states(self.function_states)
                        if failure:self.error(ValueError('E_INPUT_LOCATION'))
                        else:dispatch(selected)
                        return False
                    GLib.idle_add(finish)
                threading.Thread(target=copy_inputs,daemon=True).start()
            picker.connect('response',response); picker.show()

        def choose_output(self,key):
            """Werkzeuge ohne Quelldatei beginnen mit der Auswahl des PDF-Ziels."""
            path=output_suggestion(key,self.config.get('output_dir'))
            def selected(target):
                if not Path(target).suffix:target+='.pdf'
                self.tool_dialog(key,[],target)
            self._target_dialog=select_save_target(self.window,self.tr('save_as'),path,selected,self.error,self.tr('save'))

        def tool_dialog(self,key,selected_files=None,output_path=None,on_complete=None,on_cancel=None):
            yes,reason,detail=can_dispatch(key,self.busy)
            if not yes:
                self.message('missing',self.tr(reason)+(': '+detail if detail else ''))
                self.check_tools()
                return
            if key=='create':
                try:self._creator=open_creator(self)
                except Exception as exc:self.error(exc)
                return
            if key=='overlay':
                try:self._overlay=open_overlay(self,selected_files)
                except Exception as exc:self.error(exc)
                return
            if key=='compare':
                try:
                    self._comparison=open_comparison(self,selected_files)
                except Exception as exc:self.error(exc)
                return
            if key=='images_pdf' and selected_files is None:
                def pdf_selected(files):
                    try:self._signature=open_signature(self,files[0])
                    except Exception as exc:self.error(exc)
                self.choose_files(tool='crop',on_selected=pdf_selected,selection_title=self.tr('choose_background_pdf'))
                return
            info=BY_ID[key]
            if info[4] in ('one','many','two') and selected_files is None:
                self.choose_files(tool=key); return
            if info[4] in ('none','url') and output_path is None:
                self.choose_output(key);return
            if key=='document_info':
                self._document_information=open_document_information(self,selected_files[0]);return
            if key=='convert':
                try:self._converter=open_converter(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='edit':
                # Direkt nach der Dateiauswahl Draw starten, ohne Zwischen-
                # oder Erfolgsmeldung. Fehler bleiben sichtbar und im Log.
                try: process('edit',selected_files,None)
                except Exception as exc: self.error(exc)
                return
            if key=='signature_image':
                try:self._signature=open_signature(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='annotations':
                try:self._annotations=open_annotations(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='numbers':
                try:self._numbers=open_page_numbers(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='watermark':
                try:self._watermark=open_watermark(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='text_search':
                try:self._text_search=open_text_search(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key in ('image_resize','image_rotate','image_crop'):
                try:self._image_layout=open_image_layout(self,[],selected_files[0],existing=True,rotation_mode=key=='image_rotate',crop_mode=key=='image_crop')
                except Exception as exc:self.error(exc)
                return
            if key=='extract_images':
                try:self._image_extractor=open_image_extractor(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='images_pdf':
                try:self._image_layout=open_image_layout(self,selected_files)
                except Exception as exc:self.error(exc)
                return
            if key=='crop':
                try:self._cropper=open_cropper(self,selected_files[0])
                except Exception as exc:self.error(exc)
                return
            if key=='redact':
                try:
                    self._redactor=open_redactor(self,selected_files[0],output_suggestion('redact',self.config.get('output_dir')))
                except Exception as exc:self.error(exc)
                return
            if key=='form':
                try:
                    form_report=analyse_form(selected_files[0])
                    if form_report['mode']=='none':
                        self.message('form',self.tr('E_FORM_NONE'));return
                except Exception as exc:self.error(exc);return
            if key=='decrypt':
                try: security=pdf_security(selected_files[0])
                except Exception as exc:self.error(exc);return
            if key=='optimize':
                try:
                    optimization_report=analyse_optimization(selected_files[0])
                except Exception as exc:self.error(exc);return
            if key=='split':
                try: split_count=pdf_page_count(selected_files[0])
                except Exception as exc:
                    logging.error('PDF split input %s: %s',selected_files,type(exc).__name__)
                    self.error(exc); return
            dialog=Gtk.Window(title=self.tr(key),transient_for=self.window,modal=True,default_width=640)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
            for prop in ('margin_start','margin_end','margin_top','margin_bottom'): getattr(box,'set_'+prop)(20)
            options_scroll=Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,propagate_natural_height=True,max_content_height=750)
            options_scroll.set_child(box);dialog.set_child(options_scroll)
            if key in ('compare','redact','compress','convert'):
                box.append(Gtk.Label(label=self.tr('note_'+key),wrap=True,xalign=0))
            if key=='form':
                summary=self.tr('form_existing' if form_report['mode']=='existing' else 'form_detected').format(text=form_report['text'],checkbox=form_report['checkbox'],pages=form_report['pages'])
                if form_report['mode']=='detected' and form_report['unrecognized']:
                    summary+='\n'+self.tr('form_partial').format(pages=', '.join(map(str,form_report['unrecognized'])))
                box.append(Gtk.Label(label=summary,wrap=True,xalign=0,max_width_chars=65))
                box.append(Gtk.Label(label=self.tr('form_note'),wrap=True,xalign=0,max_width_chars=65))
            selected=list(selected_files or []); fields={}; option_getters={}
            def field(name,default=''):
                box.append(Gtk.Label(label=self.tr(name),xalign=0))
                entry=Gtk.Entry(text=default,visibility=name!='password'); box.append(entry); fields[name]=entry
            def choice(name,items,default):
                box.append(Gtk.Label(label=self.tr(name),xalign=0))
                codes=[code for code,label in items]
                dropdown=Gtk.DropDown.new_from_strings([self.tr(label) for code,label in items])
                dropdown.set_selected(codes.index(default));box.append(dropdown)
                option_getters[name]=lambda:codes[dropdown.get_selected()]
                return dropdown
            def toggle(name):
                checkbox=Gtk.CheckButton(label=self.tr(name));box.append(checkbox)
                option_getters[name]=checkbox.get_active
                return checkbox
            if key=='merge':
                dialog.set_title(self.tr('merge_order'))
                box.append(Gtk.Label(label=self.tr('merge_order_note'),wrap=True,xalign=0))
                listing=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
                listing.add_css_class('boxed-list')
                scroll=Gtk.ScrolledWindow(min_content_height=220,max_content_height=360,propagate_natural_height=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
                scroll.set_child(listing); box.append(scroll)
                controls=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
                box.append(controls)
                buttons={}
                def refresh_selection(*_):
                    row=listing.get_selected_row(); index=row.get_index() if row else -1
                    buttons['move_up'].set_sensitive(index>0)
                    buttons['move_down'].set_sensitive(0<=index<len(selected)-1)
                    buttons['remove'].set_sensitive(index>=0)
                    run.set_sensitive(len(selected)>=2)
                def refresh_rows(index=0):
                    while listing.get_first_child(): listing.remove(listing.get_first_child())
                    for position,path in enumerate(selected,1):
                        content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3,margin_start=10,margin_end=10,margin_top=8,margin_bottom=8)
                        content.append(Gtk.Label(label=f'{position}. {Path(path).name}',xalign=0,wrap=True))
                        detail=Gtk.Label(label=str(Path(path).parent),xalign=0,wrap=True)
                        detail.add_css_class('dim-label'); content.append(detail)
                        listing.append(content)
                    if selected: listing.select_row(listing.get_row_at_index(min(index,len(selected)-1)))
                    refresh_selection()
                def move(delta):
                    row=listing.get_selected_row()
                    if not row: return
                    index=row.get_index(); target=index+delta
                    if 0<=target<len(selected):
                        selected[index],selected[target]=selected[target],selected[index]
                        refresh_rows(target)
                def remove():
                    row=listing.get_selected_row()
                    if row:
                        index=row.get_index(); selected.pop(index); refresh_rows(index)
                def append_files(paths):
                    first=len(selected)
                    selected.extend(p for p in paths if p not in selected)
                    refresh_rows(first)
                for name,callback in [('move_up',lambda:move(-1)),('move_down',lambda:move(1)),('remove',remove),('add_pdfs',lambda:self.choose_files(dialog,append_files))]:
                    button=Gtk.Button(label=self.tr(name)); buttons[name]=button
                    button.connect('clicked',lambda _,fn=callback:fn()); controls.append(button)
                listing.connect('row-selected',refresh_selection)
            elif key=='split':
                dialog.set_title(self.tr('split_options'))
                box.append(Gtk.Label(label=str(selected[0]),wrap=True,xalign=0,selectable=True))
                box.append(Gtk.Label(label=self.tr('split_page_count').format(count=split_count),xalign=0))
                box.append(Gtk.Label(label=self.tr('split_zip_note'),wrap=True,xalign=0))
                split_buttons={}; split_entries={}
                group=None
                for mode,parameter,default in [('single',None,''),('chunks','split_size','2'),('cuts','split_cuts',''),('ranges','split_ranges','')]:
                    button=Gtk.CheckButton(label=self.tr('split_'+mode))
                    if group: button.set_group(group)
                    else: group=button
                    split_buttons[mode]=button; box.append(button)
                    if parameter:
                        entry=Gtk.Entry(text=default,placeholder_text=self.tr(parameter+'_hint'))
                        fields[parameter]=entry;split_entries[mode]=entry;box.append(entry)
                preview=Gtk.Label(wrap=True,xalign=0);box.append(preview)
                def split_options():
                    return {'split_mode':next((m for m,b in split_buttons.items() if b.get_active()),'single'),**{p:e.get_text() for p,e in fields.items() if p.startswith('split_')}}
                def update_split(*_):
                    for mode,entry in split_entries.items(): entry.set_sensitive(split_buttons[mode].get_active())
                    try:
                        groups=split_groups(split_count,split_options())
                        descriptions=[]
                        for pages_in_part in groups[:5]:
                            descriptions.append(', '.join(str(n+1) for n in pages_in_part[:8])+(' …' if len(pages_in_part)>8 else ''))
                        preview.set_text(self.tr('split_preview').format(count=len(groups))+'\n'+' | '.join(descriptions)+(' …' if len(groups)>5 else ''))
                        run.set_sensitive(True)
                    except ValueError:
                        preview.set_text(self.tr('E_SPLIT'));run.set_sensitive(False)
                split_buttons['single'].set_active(True)
            elif info[4]=='url': field('url','https://')
            elif info[4]!='none':
                chosen=Gtk.Label(label='\n'.join(f'{i+1}. {p}' for i,p in enumerate(selected)),wrap=True,xalign=0,selectable=True)
                button=Gtk.Button(label=self.tr('change_files'),halign=Gtk.Align.START)
                def replaced(paths):
                    if key in ('form','decrypt','optimize'):
                        dialog.destroy();self.tool_dialog(key,paths);return
                    selected[:]=paths
                    chosen.set_text('\n'.join(f'{i+1}. {p}' for i,p in enumerate(selected)))
                def choose(*_):
                    self.choose_files(dialog,replaced,key)
                button.connect('clicked',choose); button.set_sensitive(on_complete is None); box.append(button); box.append(chosen)
                if info[4] in ('many','two'): box.append(Gtk.Label(label=self.tr('order_note'),wrap=True,xalign=0))
            if key=='pdfa_check':
                box.append(Gtk.Label(label=self.tr('pdfa_check_note'),wrap=True,xalign=0,max_width_chars=65))
            elif key=='pdfa':
                box.append(Gtk.Label(label=self.tr('pdfa_note'),wrap=True,xalign=0,max_width_chars=65))
            elif key=='compress':
                box.append(Gtk.Label(label=self.tr('engine_compress'),wrap=True,xalign=0))
                choice('gs_profile',[(code,'gs_'+code) for code in ('ebook','screen','printer','prepress','default')],'ebook')
            elif key=='ocr':
                box.append(Gtk.Label(label=self.tr('engine_ocr'),wrap=True,xalign=0))
                installed_languages=ocr_languages()
                preferred='+'.join(code for code in ('deu','eng') if code in installed_languages)
                language_options=[(code,code) for code in installed_languages]
                if '+' in preferred: language_options.insert(0,(preferred,preferred))
                if not language_options:
                    dialog.destroy();self.message('E_OCR_LANGUAGE',self.tr('E_OCR_LANGUAGE'));return
                choice('ocr_language',language_options,preferred or installed_languages[0])
                mode=choice('ocr_mode',[('skip','ocr_skip'),('redo','ocr_redo')],'skip')
                choice('ocr_output',[('pdf','ocr_pdf'),('pdfa','ocr_pdfa')],'pdf')
                choice('ocr_optimize',[(str(i),'ocr_opt_'+str(i)) for i in range(4)],'1')
                toggle('ocr_rotate');deskew=toggle('ocr_deskew')
                def adjust_deskew(*_):
                    allowed=option_getters['ocr_mode']()=='skip'
                    if not allowed: deskew.set_active(False)
                    deskew.set_sensitive(allowed)
                mode.connect('notify::selected',adjust_deskew)
                box.append(Gtk.Label(label=self.tr('ocr_options_note'),wrap=True,xalign=0))
            elif key=='pdf_images':
                choice('image_dpi',[(str(dpi),str(dpi)+' dpi') for dpi in (72,144,150,300)],'144')
            elif key=='optimize':
                box.append(Gtk.Label(label=self.tr('opt_analysis').format(**optimization_report),wrap=True,xalign=0,max_width_chars=65))
                choice('opt_structure',[('0','opt_structure_0'),('1','opt_structure_1'),('3','opt_structure_3'),('4','opt_structure_4')],'4')
                for name,enabled,active in [
                    ('opt_compress',True,True),
                    ('opt_images',bool(optimization_report['images']),True),
                    ('opt_font_compress',bool(optimization_report['embedded_fonts']),True),
                    ('opt_fonts',bool(optimization_report['full_fonts']),False),
                    ('opt_metadata',optimization_report['metadata'],False),
                    ('opt_attachments',bool(optimization_report['attachments']),False)]:
                    check=toggle(name);check.set_sensitive(enabled);check.set_active(enabled and active)
                    if not enabled:check.set_tooltip_text(self.tr('opt_unavailable'))
                box.append(Gtk.Label(label=self.tr('opt_note'),wrap=True,xalign=0,max_width_chars=65))
            if 'pages' in info[5]: field('pages')
            if 'angle' in info[5]: field('angle','90')
            if key=='decrypt':
                state='decrypt_locked' if security['locked'] else ('decrypt_restricted' if security['encrypted'] else 'decrypt_plain')
                box.append(Gtk.Label(label=self.tr(state),wrap=True,xalign=0,max_width_chars=65))
                if security['locked']:
                    field('password')
                    show=Gtk.CheckButton(label=self.tr('show_password'))
                    show.connect('toggled',lambda b:fields['password'].set_visibility(b.get_active()));box.append(show)
                elif security['encrypted']:
                    method=choice('decrypt_method',[('without','decrypt_without_option'),('password','decrypt_password_option')],'without')
                    field('password');fields['password'].set_sensitive(False)
                    def method_changed(*_):
                        using_password=option_getters['decrypt_method']()=='password'
                        fields['password'].set_sensitive(using_password)
                        if not using_password:fields['password'].set_text('')
                    method.connect('notify::selected',method_changed)
                    box.append(Gtk.Label(label=self.tr('decrypt_without'),wrap=True,xalign=0,max_width_chars=65))
            elif info[5]=='password': field('password')
            if key=='watermark':
                box.append(Gtk.Label(label=self.tr('watermark_note'),wrap=True,xalign=0,max_width_chars=65))
                field('text')
                def watermark_number(name,value,lower,upper):
                    box.append(Gtk.Label(label=self.tr(name),xalign=0))
                    spin=Gtk.SpinButton.new_with_range(lower,upper,1);spin.set_value(value);box.append(spin)
                    option_getters[name]=spin.get_value
                watermark_number('watermark_angle',45,-90,90)
                watermark_number('watermark_size',72,8,200)
                watermark_number('watermark_opacity',20,1,100)
                choice('watermark_color',[('gray','watermark_gray'),('red','watermark_red'),('blue','watermark_blue')],'gray')
            elif info[5]=='text': field('text')
            if info[5] not in ('external','check'):
                suffix='.zip' if key in ZIP_TOOLS else '.pdf'
                field('output',output_path or str(output_suggestion(key,self.config.get('output_dir'))))
                browse=Gtk.Button(label=self.tr('save_as'),halign=Gtk.Align.START)
                def save_as(*_):
                    self._target_dialog=select_save_target(dialog,self.tr('save_as'),fields['output'].get_text(),fields['output'].set_text,self.error,self.tr('save'))
                browse.connect('clicked',save_as); box.append(browse)
            run=Gtk.Button(label=self.tr('finish'),halign=Gtk.Align.END)
            run.add_css_class('suggested-action'); box.append(run)
            progress=Gtk.Label(wrap=True); box.append(progress)
            cancel_event=threading.Event()
            cancel_button=Gtk.Button(label=self.tr('cancel'),halign=Gtk.Align.END,visible=False)
            cancel_button.connect('clicked',lambda *_:(cancel_event.set(),cancel_button.set_sensitive(False)))
            cancel_area=Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            cancel_area.append(cancel_button)
            options_scroll.set_child(None);dialog.set_child(None)
            outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);outer.append(options_scroll);outer.append(cancel_area)
            options_scroll.set_child(box);dialog.set_child(outer)
            completed=False
            def closing(*_):
                if self.busy:return True
                if on_cancel and not completed:on_cancel()
                return False
            dialog.connect('close-request',closing)
            def execute(*_):
                opts={k:v.get_text() for k,v in fields.items()}
                opts.update({name:getter() for name,getter in option_getters.items()})
                if key=='split': opts.update(split_options())
                inputs=[opts['url']] if 'url' in opts else list(selected)
                yes,reason,detail=can_dispatch(key,self.busy)
                if not yes:
                    self.message('missing',self.tr(reason)+(': '+detail if detail else ''));return
                self.busy=True; self.apply_function_states(self.function_states)
                cancel_event.clear();opts['cancel_event']=cancel_event;cancel_button.set_visible(True);cancel_button.set_sensitive(True)
                box.set_sensitive(False); progress.set_text(self.tr('working'))
                def work():
                    error=None
                    try: validation_result=process(key,inputs,opts.get('output'),opts)
                    except Exception as exc:
                        error=exc
                        logging.error('Operation %s, inputs %s, output %s: %s',key,inputs,opts.get('output'),type(exc).__name__)
                    def finish():
                        nonlocal completed
                        self.busy=False; box.set_sensitive(True)
                        self.apply_function_states(self.function_states);self.check_tools()
                        cancel_button.set_visible(False)
                        if error:
                            if str(error)=='E_CANCELLED':progress.set_text(self.tr('E_CANCELLED'))
                            else:progress.set_text('');self.error(error)
                        else:
                            completed=True;dialog.destroy()
                            if key=='pdfa_check':self.message('pdfa_check',self.tr('pdfa_check_passed').format(profile=validation_result))
                            elif on_complete:on_complete(opts['output'])
                            else:self.message('done',self.tr('opened') if info[5]=='external' else self.tr('pdfa_verified' if key=='pdfa' else 'saved')+'\n'+opts['output'])
                        return False
                    GLib.idle_add(finish)
                threading.Thread(target=work,daemon=True).start()
            run.connect('clicked',execute)
            if key=='decrypt' and security['locked']:
                run.set_sensitive(False)
                fields['password'].connect('changed',lambda e:run.set_sensitive(bool(e.get_text())))
            if key=='merge': refresh_rows()
            if key=='split':
                for button in split_buttons.values(): button.connect('toggled',update_split)
                for entry in split_entries.values(): entry.connect('changed',update_split)
                update_split()
            def validate_inputs(*_):
                if key in ('merge','split'):return
                valid=all(Path(path).is_file() for path in selected)
                if info[4]=='one':valid=valid and len(selected)==1
                if info[4]=='two':valid=valid and len(selected)==2
                if info[4]=='many':valid=valid and bool(selected)
                if 'output' in fields:
                    destination=Path(fields['output'].get_text()).expanduser()
                    valid=valid and bool(fields['output'].get_text().strip()) and destination.parent.is_dir() and not destination.exists()
                if 'password' in fields:
                    valid=valid and bool(fields['password'].get_text())
                if 'url' in fields:
                    valid=valid and fields['url'].get_text().startswith(('https://','http://'))
                run.set_sensitive(valid)
            for entry in fields.values():entry.connect('changed',validate_inputs)
            validate_inputs()
            dialog.present()
            return dialog

        def workflow(self):
            """Geordnete Schritte: gespeicherte PDF ohne erneute Dateiauswahl weitergeben.

            Einzelne Ergebnisse bleiben erhalten, auch nach Abbruch oder Fehlern.
            Externe Editoren und ZIP-Ausgaben haben keinen eindeutigen PDF-Rückgabepfad.
            """
            if self.busy:
                self.message('busy',self.tr('wait'));return
            self.choose_files(tool='optimize',on_selected=self.workflow_options)

        def workflow_options(self,paths):
            allowed=[t[0] for t in TOOLS if t[4]=='one' and t[5]!='external' and t[0] not in ZIP_TOOLS and t[0] not in ('convert','redact','web')]
            window=Gtk.Window(title=self.tr('workflow'),transient_for=self.window,modal=True,default_width=680)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_top=20,margin_bottom=20,margin_start=20,margin_end=20)
            window.set_child(box)
            box.append(Gtk.Label(label=paths[0],wrap=True,xalign=0))
            box.append(Gtk.Label(label=self.tr('workflow_note'),wrap=True,xalign=0,max_width_chars=70))
            available_keys=[k for k in allowed if can_dispatch(k)[0]]
            dropdown=Gtk.DropDown.new_from_strings([self.tr(k) for k in available_keys]);box.append(dropdown)
            add=Gtk.Button(label=self.tr('workflow_add'),halign=Gtk.Align.START);box.append(add)
            listing=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            scroll=Gtk.ScrolledWindow(min_content_height=180,max_content_height=300,propagate_natural_height=True);scroll.set_child(listing);box.append(scroll)
            queue=[]
            controls=Gtk.Box(spacing=8);box.append(controls)
            start=Gtk.Button(label=self.tr('workflow_start'),halign=Gtk.Align.END);box.append(start);start.set_sensitive(False)
            def refresh(index=0):
                while listing.get_first_child():listing.remove(listing.get_first_child())
                for i,key in enumerate(queue):listing.append(Gtk.Label(label=f'{i+1}. '+self.tr(key),xalign=0,margin_top=8,margin_bottom=8))
                if queue:listing.select_row(listing.get_row_at_index(max(0,min(index,len(queue)-1))))
                start.set_sensitive(bool(queue))
            def append(*_):
                queue.append(available_keys[dropdown.get_selected()]);refresh(len(queue)-1)
            add.set_sensitive(bool(available_keys));add.connect('clicked',append)
            def move(delta):
                row=listing.get_selected_row()
                if not row:return
                i=row.get_index();j=i+delta
                if 0<=j<len(queue):queue[i],queue[j]=queue[j],queue[i];refresh(j)
            def remove(*_):
                row=listing.get_selected_row()
                if row:i=row.get_index();queue.pop(i);refresh(i)
            for label,callback in [('workflow_up',lambda *_:move(-1)),('workflow_down',lambda *_:move(1)),('workflow_remove',remove)]:
                button=Gtk.Button(label=self.tr(label));button.connect('clicked',callback);controls.append(button)
            def begin(*_):
                window.destroy();self.workflow_next(list(queue),paths[0],1,len(queue))
            start.connect('clicked',begin);window.present()

        def workflow_next(self,queue,current,step,total):
            if not queue:
                self.message('done',self.tr('saved')+'\n'+current);return
            key=queue[0]
            def advance(result):
                GLib.idle_add(lambda:(self.workflow_next(queue[1:],result,step+1,total),False)[1])
            def cancelled():
                self.message('workflow',self.tr('workflow_stopped')+'\n'+current)
            dialog=self.tool_dialog(key,[current],on_complete=advance,on_cancel=cancelled)
            if dialog:dialog.set_title(f'{step}/{total} · '+self.tr(key))

        def show_logs(self):
            """Aktuelles Sitzungslog schreibgeschützt anzeigen und bei Bedarf neu laden."""
            dialog=Gtk.Window(title=self.tr('show_logs'),transient_for=self.window,default_width=850,default_height=480)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
            for side in ('top','bottom','start','end'): getattr(box,'set_margin_'+side)(12)
            dialog.set_child(box)
            path=STATE/'logs/mintpdf.log'
            label=Gtk.Label(label=str(path),xalign=0,selectable=True);box.append(label)
            view=Gtk.TextView(editable=False,cursor_visible=False,monospace=True,wrap_mode=Gtk.WrapMode.WORD_CHAR)
            scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(view);box.append(scroll)
            def refresh(*unused):
                try:
                    for handler in logging.getLogger().handlers: handler.flush()
                    content=path.read_text(encoding='utf-8')
                    view.get_buffer().set_text(content or self.tr('empty_log'))
                except (OSError,UnicodeError): view.get_buffer().set_text(self.tr('E_LOG'))
            row=Gtk.Box(spacing=8,halign=Gtk.Align.END);box.append(row)
            button=Gtk.Button(label=self.tr('refresh_logs'));button.connect('clicked',refresh);row.append(button)
            close=Gtk.Button(label=self.tr('close_logs'));close.connect('clicked',lambda *_:dialog.destroy());row.append(close)
            refresh();dialog.present()

        def output_settings(self):
            return self.settings()

        def settings(self):
            self.scan_languages()
            dialog=Gtk.Window(title=self.tr('settings'),transient_for=self.window,modal=True,default_width=640,default_height=640)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
            for prop in ('margin_start','margin_end','margin_top','margin_bottom'): getattr(box,'set_'+prop)(20)
            outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
            scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
            scroll.set_child(box);outer.append(scroll);dialog.set_child(outer)
            box.append(Gtk.Label(label=self.tr('settings_output'),xalign=0))
            box.append(Gtk.Label(label=self.tr('output_folder_note'),wrap=True,xalign=0,max_width_chars=65))
            output_entry=Gtk.Entry(text=self.config.get('output_dir',str(Path.home()/'Downloads')))
            box.append(output_entry)
            choose=Gtk.Button(label=self.tr('choose_folder'),halign=Gtk.Align.START);box.append(choose)
            def browse(*_):
                picker=Gtk.FileChooserNative(title=self.tr('choose_folder'),transient_for=dialog,modal=True,action=Gtk.FileChooserAction.SELECT_FOLDER,accept_label=self.tr('open'),cancel_label=self.tr('cancel'))
                current=Path(output_entry.get_text()).expanduser()
                if current.is_dir():picker.set_current_folder(Gio.File.new_for_path(str(current)))
                def response(p,r):
                    if r==Gtk.ResponseType.ACCEPT:
                        file=p.get_file()
                        if file and file.get_path():output_entry.set_text(file.get_path())
                    p.destroy()
                picker.connect('response',response);picker.show()
            choose.connect('clicked',browse)
            box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL,margin_top=8,margin_bottom=8))
            box.append(Gtk.Label(label=self.tr('settings_language'),xalign=0))
            dialog.output_entry=output_entry
            codes=sorted(self.langs)
            combo=None
            language_slot=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
            box.append(language_slot)
            def refresh_languages():
                nonlocal combo
                while language_slot.get_first_child(): language_slot.remove(language_slot.get_first_child())
                codes[:]=sorted(self.langs)
                combo=None
                if len(codes)>1:
                    language_slot.append(Gtk.Label(label=self.tr('language'),xalign=0))
                    combo=Gtk.DropDown.new_from_strings([self.langs[c].get('language_name',c) for c in codes])
                    combo.set_selected(codes.index(self.language)); language_slot.append(combo)
            refresh_languages()
            box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL,margin_top=8,margin_bottom=8))
            box.append(Gtk.Label(label=self.tr('download_title'),xalign=0))
            box.append(Gtk.Label(label=self.tr('download_note'),wrap=True,xalign=0))
            source=Gtk.Entry(text=self.config.get('github_source',''),placeholder_text='https://raw.githubusercontent.com/OWNER/REPO/REF')
            box.append(source)
            language=Gtk.Entry(placeholder_text=self.tr('language_code_hint')); box.append(language)
            download=Gtk.Button(label=self.tr('download'),halign=Gtk.Align.START); box.append(download)
            status=Gtk.Label(wrap=True); box.append(status)
            def fetch(*_):
                root=source.get_text().strip().rstrip('/'); code=language.get_text().strip()
                if not re.fullmatch(r'https://raw\.githubusercontent\.com/[\w.-]+/[\w.-]+/[\w./-]+',root) or not re.fullmatch('[a-z]{2}',code):
                    self.message('E_DOWNLOAD',self.tr('E_DOWNLOAD')); return
                download.set_sensitive(False); status.set_text(self.tr('working'))
                def worker():
                    error=None
                    try: download_language(root,code)
                    except Exception as exc: error=exc
                    def finish():
                        download.set_sensitive(True)
                        if error: self.error(error); status.set_text(self.tr('E_DOWNLOAD'))
                        else:
                            self.scan_languages(); refresh_languages()
                            status.set_text(self.tr('done'))
                    GLib.idle_add(finish)
                threading.Thread(target=worker,daemon=True).start()
            download.connect('clicked',fetch)
            buttons=Gtk.Box(spacing=8,halign=Gtk.Align.END,margin_start=20,margin_end=20,margin_bottom=20)
            outer.append(buttons)
            cancel=Gtk.Button(label=self.tr('cancel'));cancel.connect('clicked',lambda *_:dialog.close());buttons.append(cancel)
            save=Gtk.Button(label=self.tr('save'));save.add_css_class('suggested-action');buttons.append(save)
            dialog.save_button=save;dialog.cancel_button=cancel
            def persist(*_):
                try:
                    folder=validate_output_folder(output_entry.get_text())
                    selected_language=codes[combo.get_selected()] if combo else self.language
                    config={**self.config,'output_dir':folder,'language':selected_language,'github_source':source.get_text().strip()}
                    write_settings(config)
                except Exception as exc:self.error(exc);return
                self.config=config;self.language=selected_language
                dialog.destroy();self.build()
            save.connect('clicked',persist); dialog.present();return dialog

        def help(self):
            path=STATE/'help'/f'{self.language}.html'
            if not path.exists(): path=BASE/'help'/f'{self.language}.html'
            try:
                text=path.read_text(encoding='utf-8')
                if '<html' not in text.lower(): raise ValueError('E_HELP')
                Gio.AppInfo.launch_default_for_uri(path.as_uri(),None)
            except Exception: self.message('E_HELP',self.tr('E_HELP'))

        def about(self):
            dialog=Gtk.AboutDialog(transient_for=self.window,modal=True,program_name='mintPDF',version=VERSION,authors=['Josef Lehner'],website='https://dogtruck.eu',website_label='dogtruck.eu',license_type=Gtk.License.GPL_3_0_ONLY,title=self.tr('about')+' mintPDF')
            path=BASE/'resources/mintpdf.png'
            if path.exists(): dialog.set_logo(Gdk.Texture.new_from_filename(str(path)))
            dialog.present()

        def info(self):
            old=getattr(self,'_info_dialog',None)
            if old is not None:old.present();return old
            try:
                tools=json.loads((BASE/'projekt.json').read_text())['tool_info']
                if not isinstance(tools,list):raise ValueError('E_CONFIG')
            except (OSError,ValueError,KeyError) as exc:
                self.error(exc);return None
            if not tools:return None
            dialog=Gtk.Window(title=self.tr('info'),transient_for=self.window,default_width=620,default_height=460)
            dialog.set_name('tool_info_dialog');self._info_dialog=dialog
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=18,margin_end=18,margin_top=18,margin_bottom=18)
            dialog.set_child(box)
            heading=Gtk.Box(spacing=10)
            heading.append(Gtk.Image.new_from_icon_name('dialog-information-symbolic'))
            heading.append(Gtk.Label(label=self.tr('tool_info_title'),xalign=0,wrap=True))
            box.append(heading)
            scroll=Gtk.ScrolledWindow(vexpand=True,hscrollbar_policy=Gtk.PolicyType.NEVER)
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
            scroll.set_child(content);box.append(scroll)
            loading=Gtk.Label(label=self.tr('tool_info_loading'),xalign=0);content.append(loading)
            close=Gtk.Button(label=self.tr('close'),halign=Gtk.Align.END)
            close.connect('clicked',lambda *_:dialog.close());box.append(close)
            def closed(*_):
                self._info_dialog=None
                return False
            dialog.connect('close-request',closed)
            def present(results):
                if getattr(self,'_info_dialog',None) is not dialog:return False
                content.remove(loading)
                for tool in results:
                    row=Gtk.Box(spacing=10)
                    icon=Gtk.Image.new_from_icon_name('emblem-ok-symbolic' if tool['available'] else 'dialog-warning-symbolic')
                    icon.set_valign(Gtk.Align.START);row.append(icon)
                    details=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=3,hexpand=True)
                    status=self.tr('tool_available' if tool['available'] else 'tool_missing')
                    details.append(Gtk.Label(label=tool['name']+' — '+status,xalign=0,wrap=True))
                    details.append(Gtk.Label(label=self.tr('tool_version')+': '+(tool['version'] or self.tr('unknown')),xalign=0,wrap=True,selectable=True))
                    if tool.get('apt'):details.append(Gtk.Label(label='APT: '+tool['apt'],xalign=0,wrap=True,selectable=True))
                    if tool.get('optional'):details.append(Gtk.Label(label=self.tr('tool_optional'),xalign=0,wrap=True))
                    if tool.get('note_key'):details.append(Gtk.Label(label=self.tr(tool['note_key']),xalign=0,wrap=True))
                    if tool.get('error'):details.append(Gtk.Label(label=self.tr(tool['error']),xalign=0,wrap=True))
                    row.append(details);content.append(row)
                dialog.tool_results=results
                return False
            def worker():
                from core import inspect_tool
                GLib.idle_add(present,[inspect_tool(tool) for tool in tools])
            threading.Thread(target=worker,daemon=True).start()
            dialog.present()
            return dialog
    return App().run([sys.argv[0]])


def download_language(root,code):
    """Nur fehlende Sprachressourcen installieren, Downloadreste immer entfernen."""
    import html.parser
    class HtmlCheck(html.parser.HTMLParser):
        language=None
        def handle_starttag(self,tag,attrs):
            if tag=='html': self.language=dict(attrs).get('lang')
    try:
        try: downloads=Path(subprocess.check_output(['xdg-user-dir','DOWNLOAD'],text=True).strip())
        except (OSError,subprocess.SubprocessError): downloads=Path.home()/'Downloads'
        downloads.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='mintpdf-language-',dir=downloads) as tmp:
            pending=[]
            for directory,suffix in [('languages','json'),('help','html')]:
                dest=STATE/directory/f'{code}.{suffix}'
                if dest.exists() or (BASE/directory/dest.name).exists(): continue
                request=urllib.request.Request(f'{root}/{directory}/{code}.{suffix}',headers={'User-Agent':'mintPDF/'+VERSION})
                with urllib.request.urlopen(request,timeout=20) as response:
                    data=response.read(2_000_001)
                if len(data)>2_000_000: raise ValueError('E_DOWNLOAD')
                text=data.decode('utf-8')
                path=Path(tmp)/dest.name; path.write_text(text,encoding='utf-8')
                if suffix=='json':
                    parsed=read_json(path)
                    if parsed.get('language_code')!=code: raise ValueError('E_DOWNLOAD')
                else:
                    checker=HtmlCheck(); checker.feed(text)
                    if checker.language!=code or '</html>' not in text.lower(): raise ValueError('E_DOWNLOAD')
                pending.append((path,dest))
            installed=[]
            try:
                for path,dest in pending:
                    # Auf dem Ziellaufwerk vorbereiten; ein Link veröffentlicht
                    # ausschließlich vollständige Dateien ohne Überschreiben.
                    fd,staging=tempfile.mkstemp(prefix='.mintpdf-',dir=dest.parent)
                    try:
                        with os.fdopen(fd,'wb') as stream: stream.write(path.read_bytes())
                        try:
                            os.link(staging,dest); installed.append(dest)
                        except FileExistsError: pass
                    finally: Path(staging).unlink(missing_ok=True)
            except Exception:
                for dest in installed: dest.unlink(missing_ok=True)
                raise
    except Exception as exc:
        raise RuntimeError('E_DOWNLOAD') from exc


# Kompakte, themetreue Menüs aus der gemeinsamen Vorlage.
_separator_provider=None
def style_menu_separators(menu_bar):
    from gi.repository import Gtk, Gdk
    global _separator_provider
    menu_bar.add_css_class('template-menubar')
    if _separator_provider is None:
        _separator_provider = Gtk.CssProvider()
        _separator_provider.load_from_data(b'\n            .template-menubar popover.menu separator {\n                min-height: 1px;\n                background-color: alpha(@theme_fg_color, 0.45);\n                margin-top: 4px;\n                margin-bottom: 4px;\n            }\n        ')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), _separator_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

def descendants(widget):
    from gi.repository import Gtk, Gdk
    yield widget
    child = widget.get_first_child()
    while child is not None:
        yield from descendants(child)
        child = child.get_next_sibling()

def fit_menu_scroll_area(scroll):
    from gi.repository import Gtk, Gdk
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    child = scroll.get_child()
    if child is None:
        return
    natural = child.measure(Gtk.Orientation.VERTICAL, -1).natural
    scrollbar_minimum = scroll.get_vscrollbar().measure(Gtk.Orientation.VERTICAL, -1).minimum
    if natural < scrollbar_minimum:
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)

def compact_menus(menu_bar):
    from gi.repository import Gtk, Gdk
    style_menu_separators(menu_bar)
    for widget in descendants(menu_bar):
        if isinstance(widget, Gtk.ScrolledWindow):
            fit_menu_scroll_area(widget)
            if not getattr(widget, '_template_compact_menu', False):
                widget.connect('map', fit_menu_scroll_area)
                widget._template_compact_menu = True

# Vergleichsfenster und Schwärzungsfenster (GPL-3.0-only).
def open_comparison(app, paths=None):
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_foreign('cairo')
    from gi.repository import Gtk, Gio, GLib
    import cairo

    class Comparison(Gtk.Window):

        def __init__(self):
            super().__init__(title=app.tr('compare'), transient_for=app.window, modal=True, default_width=1100, default_height=850)
            self.running = False
            self.result = None
            self.index = 0
            self.tr = app.tr
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            self.set_child(root)
            group = Gio.SimpleActionGroup()
            self.insert_action_group('comparison', group)
            menu = Gio.Menu()
            sub = Gio.Menu()
            for key, callback in [('cmp_export', self.export), ('ed_close', self.close)]:
                action = Gio.SimpleAction.new(key, None)
                action.connect('activate', lambda a, p, cb=callback: cb())
                group.add_action(action)
                sub.append(self.tr(key), 'comparison.' + key)
            menu.append_submenu(self.tr('file'), sub)
            root.append(Gtk.PopoverMenuBar.new_from_model(menu))
            self.entries = []
            self.inputs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12, margin_end=12)
            root.append(self.inputs)
            for i in range(2):
                row = Gtk.Box(spacing=8)
                row.append(Gtk.Label(label=f'PDF {i + 1}:'))
                entry = Gtk.Entry(hexpand=True)
                self.entries.append(entry)
                row.append(entry)
                button = Gtk.Button(label=self.tr('cmp_select'))
                button.connect('clicked', lambda _, n=i: self.pick(n))
                row.append(button)
                self.inputs.append(row)
                entry.connect('changed', self.invalidate)
                if paths and i < len(paths):
                    entry.set_text(paths[i])
            modes = Gtk.Box(spacing=12)
            self.inputs.append(modes)
            self.modes = {}
            first = None
            for key in COMPARISON_MODES:
                b = Gtk.CheckButton(label=self.tr('cmp_' + key))
                if first:
                    b.set_group(first)
                else:
                    first = b
                self.modes[key] = b
                modes.append(b)
                b.connect('toggled', self.invalidate)
            first.set_active(True)
            self.start = Gtk.Button(label=self.tr('cmp_run'), halign=Gtk.Align.START)
            self.start.connect('clicked', self.run)
            self.inputs.append(self.start)
            self.status = Gtk.Label(wrap=True, xalign=0, margin_start=12)
            root.append(self.status)
            self.output = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, vexpand=True)
            root.append(self.output)
            self.output.set_visible(False)
            nav = Gtk.Box(spacing=8, margin_start=12)
            self.output.append(nav)
            for label, delta in [('ed_previous', -1), ('ed_next', 1)]:
                b = Gtk.Button(label=self.tr(label))
                b.connect('clicked', lambda _, d=delta: self.navigate(d))
                nav.append(b)
            self.page_label = Gtk.Label()
            nav.append(self.page_label)
            stack = Gtk.Stack(vexpand=True)
            switch = Gtk.StackSwitcher(stack=stack, halign=Gtk.Align.CENTER)
            self.output.append(switch)
            self.output.append(stack)
            self.views = []
            for key in ('cmp_side', 'cmp_diff'):
                scroll = Gtk.ScrolledWindow()
                box = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
                scroll.set_child(box)
                self.views.append(box)
                stack.add_titled(scroll, key, self.tr(key))
            self.text = Gtk.TextView(editable=False, wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=12, right_margin=12)
            scroll = Gtk.ScrolledWindow()
            scroll.set_child(self.text)
            stack.add_titled(scroll, 'report', self.tr('cmp_report'))
            self.connect('close-request', lambda *_: self.running)
            self.present()

        def invalidate(self, *_):
            self.result = None
            if hasattr(self, 'output'):
                self.output.set_visible(False)
                self.status.set_text('')

        def pick(self, index):
            picker = Gtk.FileChooserNative(title=self.tr('choose_pdf')+f' ({index + 1}/2)', transient_for=self, modal=True, action=Gtk.FileChooserAction.OPEN, accept_label=self.tr('open'), cancel_label=self.tr('cancel'))
            f = Gtk.FileFilter()
            f.set_name('PDF')
            f.add_pattern('*.pdf')
            f.add_pattern('*.PDF')
            picker.add_filter(f)
            self.picker = picker

            def response(p, r):
                file = p.get_file() if r == Gtk.ResponseType.ACCEPT else None
                p.hide()
                p.destroy()
                if file and file.get_path():
                    self.entries[index].set_text(file.get_path())
            picker.connect('response', response)
            picker.show()

        def run(self, *_):
            self.invalidate()
            self.running = True
            self.inputs.set_sensitive(False)
            self.status.set_text(self.tr('working'))
            paths = [e.get_text() for e in self.entries]
            mode = next((k for k, b in self.modes.items() if b.get_active()))

            def worker():
                try:
                    result = compare_documents(*paths, mode)
                    error = None
                except Exception as exc:
                    result = None
                    error = exc

                def finished():
                    self.running = False
                    self.inputs.set_sensitive(True)
                    if error:
                        logging.error('PDF comparison: %s', type(error).__name__)
                        self.status.set_text('')
                        app.error(error)
                    else:
                        self.result = result
                        self.index = 0
                        self.status.set_markup('<span foreground="green">✓</span> ' + GLib.markup_escape_text(self.tr('cmp_done') + ' · ' + self.tr('cmp_' + result['mode']) + '\n' + comparison_report(result, self.tr).split(self.tr('cmp_method'))[0]))
                        self.text.get_buffer().set_text(comparison_report(result, self.tr))
                        self.output.set_visible(True)
                        self.render()
                    return False
                GLib.idle_add(finished)
            threading.Thread(target=worker, daemon=True).start()

        def navigate(self, delta):
            if self.result and 0 <= self.index + delta < len(self.result['rows']):
                self.index += delta
                self.render()

        def render(self):
            row = self.result['rows'][self.index]
            self.page_label.set_text(f'PDF 1: {(row['a'] + 1 if row['a'] is not None else '—')} | PDF 2: {(row['b'] + 1 if row['b'] is not None else '—')}')
            for v, box in enumerate(self.views):
                while box.get_first_child():
                    box.remove(box.get_first_child())
                for n, key in enumerate(('a', 'b')):
                    if row[key] is None:
                        box.append(Gtk.Label(label=self.tr('cmp_no_page')))
                        continue
                    with fitz.open(stream=self.result['sources'][n], filetype='pdf') as d:
                        pix = comparison_raster(d[row[key]])
                    surface = cairo.ImageSurface.create_from_png(io.BytesIO(pix.tobytes('png')))
                    scale = 0.65
                    area = Gtk.DrawingArea(content_width=int(pix.width * scale), content_height=int(pix.height * scale), valign=Gtk.Align.START)

                    def draw(widget, ctx, w, h, surface=surface, v=v, n=n):
                        ctx.scale(scale, scale)
                        ctx.set_source_surface(surface, 0, 0)
                        ctx.paint()
                        if v:
                            ctx.set_source_rgba(1, 0, 0, 0.28) if n == 0 else ctx.set_source_rgba(0, 0.5, 1, 0.28)
                            boxes = row['text_regions'][n] if self.result['mode'] == 'text' else row['regions']
                            if row['a'] is None or row['b'] is None:
                                boxes = [(0, 0, surface.get_width(), surface.get_height())]
                            for x0, y0, x1, y1 in boxes:
                                ctx.rectangle(x0, y0, x1 - x0, y1 - y0)
                                ctx.fill()
                    area.set_draw_func(draw)
                    box.append(area)
                if v:
                    box.append(Gtk.Label(label=self.tr('cmp_legend') if self.result['mode'] != 'technical' else self.tr('cmp_unchecked'), wrap=True, max_width_chars=18))

        def export(self):
            if not self.result:
                return
            picker = Gtk.FileChooserNative(title=self.tr('cmp_export'), transient_for=self, modal=True, action=Gtk.FileChooserAction.SAVE, accept_label=self.tr('save'), cancel_label=self.tr('cancel'))
            picker.set_current_folder(Gio.File.new_for_path(app.config.get('output_dir') or str(Path.home() / 'Downloads')))
            picker.set_current_name('mintpdf-comparison.txt')

            def response(p, r):
                file = p.get_file() if r == Gtk.ResponseType.ACCEPT else None
                p.hide()
                p.destroy()
                if file:
                    try:
                        with open(file.get_path(), 'x', encoding='utf-8') as out:
                            out.write(comparison_report(self.result, self.tr))
                    except Exception as exc:
                        app.error(ValueError('E_EXISTS') if isinstance(exc, FileExistsError) else exc)
            picker.connect('response', response)
            picker.show()
    return Comparison()

def open_redactor(app, path, output):
    from pathlib import Path
    import io, os, tempfile, logging
    import pymupdf as fitz
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, Gio, GLib
    import cairo

    class Redactor(Gtk.Window):

        def __init__(self):
            self.source = Path(path).read_bytes()
            self.doc = fitz.open(stream=self.source, filetype='pdf')
            if self.doc.needs_pass:
                self.doc.close()
                raise ValueError('E_PASSWORD')
            if not self.doc.is_pdf or not len(self.doc):
                self.doc.close()
                raise ValueError('E_INPUT')
            super().__init__(title=app.tr('redact') + ' — ' + Path(path).name, transient_for=app.window, modal=True, default_width=1050, default_height=850)
            self.tr = app.tr
            self.regions = []
            self.redo_regions = []
            self.saved = []
            self.index = 0
            self.scale = 1.0
            self.current = None
            self.picker = None
            self.surface = None
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.set_child(root)
            group = Gio.SimpleActionGroup()
            self.insert_action_group('redactor', group)
            menus = Gio.Menu()
            for title, actions in [('file', [('rd_save', self.save), ('ed_close', self.close)]), ('edit_menu', [('ed_undo', self.undo), ('ed_redo', self.redo)])]:
                sub = Gio.Menu()
                for key, callback in actions:
                    action = Gio.SimpleAction.new(key, None)
                    action.connect('activate', lambda a, p, cb=callback: cb())
                    group.add_action(action)
                    sub.append(self.tr(key), 'redactor.' + key)
                menus.append_submenu(self.tr(title), sub)
            self.actions = group
            root.append(Gtk.PopoverMenuBar.new_from_model(menus))
            nav = Gtk.Box(spacing=8, margin_start=12, margin_end=12)
            root.append(nav)

            def button(key, callback):
                b = Gtk.Button(label=self.tr(key))
                b.connect('clicked', lambda *_: callback())
                nav.append(b)
                return b
            button('ed_previous', lambda: self.navigate(-1))
            button('ed_next', lambda: self.navigate(1))
            self.page_label = Gtk.Label()
            nav.append(self.page_label)
            self.zoom = Gtk.DropDown.new_from_strings(['50 %', '75 %', '100 %', '125 %', '150 %', '200 %'])
            self.zoom.set_selected(2)
            self.zoom.connect('notify::selected', self.set_zoom)
            nav.append(self.zoom)
            self.undo_button = button('ed_undo', self.undo)
            self.redo_button = button('ed_redo', self.redo)
            self.save_button = button('rd_save', self.save)
            root.append(Gtk.Label(label=self.tr('rd_hint'), wrap=True, xalign=0, margin_start=12, margin_end=12))
            scroll = Gtk.ScrolledWindow(vexpand=True)
            root.append(scroll)
            self.canvas = Gtk.DrawingArea(halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
            self.canvas.set_draw_func(self.draw)
            scroll.set_child(self.canvas)
            drag = Gtk.GestureDrag()
            drag.set_button(1)
            drag.connect('drag-begin', self.begin)
            drag.connect('drag-update', self.update)
            drag.connect('drag-end', self.end)
            self.canvas.add_controller(drag)
            self.status = Gtk.Label(wrap=True, margin_bottom=10)
            root.append(self.status)
            self.connect('close-request', self.closing)
            self.render()
            self.present()

        def refresh(self):
            self.page_label.set_text(self.tr('ed_page').format(page=self.index + 1, total=len(self.doc)))
            self.undo_button.set_sensitive(bool(self.regions))
            self.redo_button.set_sensitive(bool(self.redo_regions))
            self.save_button.set_sensitive(bool(self.regions))
            for key, enabled in [('ed_undo', bool(self.regions)), ('ed_redo', bool(self.redo_regions)), ('rd_save', bool(self.regions))]:
                self.actions.lookup_action(key).set_enabled(enabled)
            self.status.set_text(self.tr('rd_count').format(count=len(self.regions)))
            self.canvas.queue_draw()

        def render(self):
            pix = self.doc[self.index].get_pixmap(matrix=fitz.Matrix(self.scale, self.scale), alpha=False)
            self.surface = cairo.ImageSurface.create_from_png(io.BytesIO(pix.tobytes('png')))
            self.canvas.set_content_width(pix.width)
            self.canvas.set_content_height(pix.height)
            self.refresh()

        def set_zoom(self, *_):
            self.scale = [0.5, 0.75, 1, 1.25, 1.5, 2][self.zoom.get_selected()]
            self.render()

        def navigate(self, delta):
            if 0 <= self.index + delta < len(self.doc):
                self.index += delta
                self.current = None
                self.render()

        def draw(self, area, ctx, w, h):
            if self.surface:
                ctx.set_source_surface(self.surface, 0, 0)
                ctx.paint()
            if self.doc.is_closed:
                return
            rects = [fitz.Rect(r) for i, r in self.regions if i == self.index]
            if self.current:
                rects.append(self.current)
            for r in rects:
                r = r * self.doc[self.index].rotation_matrix
                ctx.set_source_rgba(0, 0, 0, 0.85)
                ctx.rectangle(r.x0 * self.scale, r.y0 * self.scale, r.width * self.scale, r.height * self.scale)
                ctx.fill()

        def point(self, x, y):
            page = self.doc[self.index]
            p = fitz.Point(x / self.scale, y / self.scale) * page.derotation_matrix
            b = page.rect * page.derotation_matrix
            return fitz.Point(min(max(p.x, 0), b.width), min(max(p.y, 0), b.height))

        def begin(self, g, x, y):
            self.origin = (x, y)
            self.start = self.point(x, y)
            self.current = None

        def update(self, g, dx, dy):
            end = self.point(self.origin[0] + dx, self.origin[1] + dy)
            self.current = fitz.Rect(min(self.start.x, end.x), min(self.start.y, end.y), max(self.start.x, end.x), max(self.start.y, end.y))
            self.canvas.queue_draw()

        def end(self, g, dx, dy):
            self.update(g, dx, dy)
            if self.current.width >= 1 and self.current.height >= 1:
                self.regions.append((self.index, tuple(self.current)))
                self.redo_regions.clear()
            self.current = None
            self.refresh()

        def undo(self):
            if self.regions:
                self.redo_regions.append(self.regions.pop())
                self.refresh()

        def redo(self):
            if self.redo_regions:
                self.regions.append(self.redo_regions.pop())
                self.refresh()

        def save(self):
            if not self.regions:
                return
            picker = Gtk.FileChooserNative(title=self.tr('rd_save'), transient_for=self, modal=True, action=Gtk.FileChooserAction.SAVE, accept_label=self.tr('save'), cancel_label=self.tr('cancel'))
            target = Path(output)
            picker.set_current_folder(Gio.File.new_for_path(str(target.parent)))
            picker.set_current_name(target.name)
            f = Gtk.FileFilter()
            f.set_name('PDF')
            f.add_pattern('*.pdf')
            picker.add_filter(f)
            self.picker = picker

            def response(p, result):
                file = p.get_file() if result == Gtk.ResponseType.ACCEPT else None
                p.hide()
                p.destroy()
                self.picker = None
                if not file:
                    return

                def write():
                    try:
                        target = file.get_path()
                        if not target:
                            raise ValueError('E_INPUT')
                        if not Path(target).suffix:
                            target += '.pdf'
                        redact_regions(self.source, target, self.regions)
                        self.saved = list(self.regions)
                        self.status.set_text(self.tr('saved') + ' ' + target)
                    except Exception as exc:
                        logging.error('PDF redaction: %s', type(exc).__name__)
                        code = str(exc) if str(exc).startswith('E_') else 'E_FILE'
                        dlg = Gtk.MessageDialog(transient_for=self, modal=True, text=code, secondary_text=self.tr(code), buttons=Gtk.ButtonsType.OK)
                        dlg.connect('response', lambda d, *_: d.destroy())
                        dlg.present()
                    return GLib.SOURCE_REMOVE
                GLib.idle_add(write)
            picker.connect('response', response)
            picker.show()

        def closing(self, *_):
            if self.regions == self.saved:
                self.doc.close()
                return False
            dlg = Gtk.MessageDialog(transient_for=self, modal=True, text=self.tr('ed_unsaved'), secondary_text=self.tr('rd_unsaved'))
            dlg.add_button(self.tr('cancel'), Gtk.ResponseType.CANCEL)
            dlg.add_button(self.tr('ed_discard'), Gtk.ResponseType.REJECT)
            dlg.set_default_response(Gtk.ResponseType.CANCEL)

            def answer(d, response):
                d.destroy()
                if response == Gtk.ResponseType.REJECT:
                    self.doc.close()
                    self.destroy()
            dlg.connect('response', answer)
            dlg.present()
            return True
    return Redactor()

def open_cropper(app,path):
    """Interaktiver Zuschnitt: Rahmen und mm-Ränder beziehen sich auf die sichtbare Seite."""
    import io
    import cairo
    import pymupdf as fitz
    import gi
    gi.require_version('Gtk','4.0');gi.require_foreign('cairo')
    from gi.repository import Gtk,Gio,GLib
    class Cropper(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            self.doc=fitz.open(stream=self.source,filetype='pdf')
            if self.doc.needs_pass:self.doc.close();raise ValueError('E_PASSWORD')
            if not self.doc.is_pdf or not len(self.doc):self.doc.close();raise ValueError('E_INPUT')
            super().__init__(title=app.tr('crop')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1050,default_height=850)
            self.index=0;self.scale=1.;self.rectangles={};self.surface=None
            self.running=False;self.valid=True;self.syncing=False;self.generation=0;self.alive=True
            self.frame=(0.,0.,1.,1.);self.drag_origin=None
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.set_child(root)
            self.actions=Gio.SimpleActionGroup();self.insert_action_group('cropper',self.actions)
            menus=Gio.Menu()
            for title,entries in [('file',[('crop_save',self.save),('ed_close',self.close)]),('edit_menu',[('crop_reset',self.reset),('crop_all',self.apply_all)]),('pages',[('ed_previous',lambda:self.navigate(-1)),('ed_next',lambda:self.navigate(1))])]:
                sub=Gio.Menu()
                for key,callback in entries:
                    action=Gio.SimpleAction.new(key,None)
                    action.connect('activate',lambda a,p,fn=callback:fn());self.actions.add_action(action)
                    sub.append(app.tr(key),'cropper.'+key)
                menus.append_submenu(app.tr(title),sub)
            bar=Gtk.PopoverMenuBar.new_from_model(menus);root.append(bar)
            bar.connect('map',lambda *_:compact_menus(bar))
            root.append(Gtk.Label(label=app.tr('crop_note'),wrap=True,xalign=0,margin_start=12,margin_end=12))
            root.append(Gtk.Label(label=app.tr('crop_limits'),wrap=True,xalign=0,margin_start=12,margin_end=12))
            grid=Gtk.Grid(column_spacing=10,row_spacing=6,margin_start=12,margin_end=12)
            self.spins={}
            for n,key in enumerate(('crop_left','crop_right','crop_top','crop_bottom')):
                label=Gtk.Label(label=app.tr(key),xalign=0)
                spin=Gtk.SpinButton.new_with_range(0,2000,.5);spin.set_digits(2)
                spin.update_property([Gtk.AccessibleProperty.LABEL],[app.tr(key)])
                self.spins[key]=spin;grid.attach(label,(n%2)*2,n//2,1,1);grid.attach(spin,(n%2)*2+1,n//2,1,1)
                spin.connect('value-changed',self.margins_changed)
            grid.attach(Gtk.Label(label=app.tr('crop_zoom'),xalign=0),0,2,1,1)
            zoom=Gtk.DropDown.new_from_strings(['50 %','75 %','100 %','125 %','150 %','200 %']);zoom.set_selected(2)
            zoom.connect('notify::selected',lambda w,*_:self.set_zoom([.5,.75,1.,1.25,1.5,2.][w.get_selected()]))
            grid.attach(zoom,1,2,1,1);root.append(grid);self.controls=grid
            self.canvas=Gtk.DrawingArea();self.canvas.set_draw_func(self.draw)
            self.canvas.update_property([Gtk.AccessibleProperty.LABEL],[app.tr('crop_note')])
            scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(self.canvas);root.append(scroll)
            drag=Gtk.GestureDrag();drag.set_button(1)
            drag.connect('drag-begin',self.drag_begin);drag.connect('drag-update',self.drag_update);drag.connect('drag-end',self.drag_end)
            self.canvas.add_controller(drag)
            self.status=Gtk.Label(wrap=True,xalign=0,margin_start=12,margin_end=12,margin_bottom=10);root.append(self.status)
            self.connect('close-request',self.closing)
            self.refresh();self.render();self.present()
        def dimensions(self):
            rect=self.doc[self.index].rect
            return rect.width,rect.height
        def refresh(self):
            self.frame=self.rectangles.get(self.index,(0.,0.,1.,1.))
            width,height=self.dimensions();x0,y0,x1,y1=self.frame;mm=25.4/72
            self.syncing=True
            for key,value in zip(('crop_left','crop_right','crop_top','crop_bottom'),(x0*width,(1-x1)*width,y0*height,(1-y1)*height)):
                self.spins[key].set_value(value*mm)
            self.syncing=False
            self.actions.lookup_action('ed_previous').set_enabled(self.index>0 and not self.running)
            self.actions.lookup_action('ed_next').set_enabled(self.index<len(self.doc)-1 and not self.running)
            for key in ('crop_save','crop_all'):self.actions.lookup_action(key).set_enabled(bool(self.rectangles) and self.valid and not self.running)
            self.actions.lookup_action('crop_reset').set_enabled(not self.running and (self.index in self.rectangles or not self.valid))
            self.status.set_text(app.tr('crop_status').format(page=self.index+1,total=len(self.doc),count=len(self.rectangles),width=(x1-x0)*width*mm,height=(y1-y0)*height*mm))
            self.canvas.queue_draw()
        def set_frame(self,frame):
            if self.running:return
            x0,y0,x1,y1=frame
            if not (0<=x0<x1<=1 and 0<=y0<y1<=1):return
            self.valid=True
            if all(abs(a-b)<1e-6 for a,b in zip(frame,(0,0,1,1))):self.rectangles.pop(self.index,None)
            else:self.rectangles[self.index]=tuple(frame)
            self.refresh()
        def margins_changed(self,*_):
            if self.syncing or self.running:return
            width,height=self.dimensions();pt=72/25.4
            left,right,top,bottom=(self.spins[k].get_value()*pt for k in ('crop_left','crop_right','crop_top','crop_bottom'))
            if left+right>=width or top+bottom>=height:
                self.valid=False
                self.actions.lookup_action('crop_save').set_enabled(False);self.actions.lookup_action('crop_all').set_enabled(False)
                self.actions.lookup_action('crop_reset').set_enabled(True)
                self.status.set_text(app.tr('crop_invalid'));return
            self.set_frame((left/width,top/height,1-right/width,1-bottom/height))
        def render(self):
            self.generation+=1;generation=self.generation;index=self.index;scale=self.scale
            width,height=self.dimensions();self.surface=None
            self.canvas.set_content_width(round(width*scale));self.canvas.set_content_height(round(height*scale))
            def worker():
                try:
                    with fitz.open(stream=self.source,filetype='pdf') as doc:data=doc[index].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png')
                    error=None
                except Exception as exc:data=None;error=exc
                def finish():
                    if not self.alive or generation!=self.generation:return False
                    if error:app.error(error)
                    else:self.surface=cairo.ImageSurface.create_from_png(io.BytesIO(data));self.canvas.queue_draw()
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def draw(self,area,ctx,width,height):
            if not self.surface:return
            ctx.set_source_surface(self.surface,0,0);ctx.paint()
            w,h=self.surface.get_width(),self.surface.get_height()
            x0,y0,x1,y1=self.frame;x0*=w;x1*=w;y0*=h;y1*=h
            ctx.set_source_rgba(.12,.12,.12,.60)
            for rectangle in ((0,0,w,y0),(0,y1,w,h-y1),(0,y0,x0,y1-y0),(x1,y0,w-x1,y1-y0)):
                ctx.rectangle(*rectangle);ctx.fill()
            ctx.set_source_rgb(.1,.65,.25);ctx.set_line_width(2);ctx.set_dash([6,4]);ctx.rectangle(x0,y0,x1-x0,y1-y0);ctx.stroke()
        def drag_begin(self,gesture,x,y):
            if self.running or not self.surface:return
            w,h=self.surface.get_width(),self.surface.get_height()
            self.drag_origin=(max(0,min(x,w)),max(0,min(y,h)))
        def drag_update(self,gesture,dx,dy):
            if self.drag_origin is None or self.running or not self.surface:return
            x,y=self.drag_origin;w,h=self.surface.get_width(),self.surface.get_height()
            endx=max(0,min(x+dx,w));endy=max(0,min(y+dy,h))
            if abs(endx-x)>=4 and abs(endy-y)>=4:self.set_frame((min(x,endx)/w,min(y,endy)/h,max(x,endx)/w,max(y,endy)/h))
        def drag_end(self,gesture,dx,dy):
            self.drag_update(gesture,dx,dy);self.drag_origin=None
        def set_zoom(self,scale):
            if not self.running:self.scale=scale;self.render()
        def navigate(self,delta):
            if not self.running and 0<=self.index+delta<len(self.doc):
                self.index+=delta;self.valid=True;self.refresh();self.render()
        def reset(self):
            self.valid=True;self.set_frame((0.,0.,1.,1.))
        def apply_all(self):
            if self.running or not self.valid:return
            frame=self.frame
            self.rectangles={i:frame for i in range(len(self.doc))} if frame!=(0.,0.,1.,1.) else {}
            self.refresh()
        def save(self):
            if not self.valid or not self.rectangles or self.running:return
            self.picker=select_save_target(self,app.tr('crop_save'),output_suggestion('crop',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            if self.running or not self.valid or not self.rectangles:return
            self.running=True;self.controls.set_sensitive(False);self.refresh()
            self.status.set_text(app.tr('working'));app.busy=True;app.apply_function_states(app.function_states)
            rectangles=dict(self.rectangles)
            def worker():
                try:
                    from core import crop_pdf
                    crop_pdf(self.source,target,rectangles);error=None
                except Exception as exc:error=exc
                def finish():
                    self.running=False;app.busy=False;app.apply_function_states(app.function_states);app.check_tools()
                    if error:self.controls.set_sensitive(True);self.refresh();app.error(error)
                    else:
                        self.rectangles.clear();self.close()
                        app.message('done',app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            if self.rectangles:
                question=Gtk.MessageDialog(transient_for=self,modal=True,text=app.tr('crop_unsaved'),buttons=Gtk.ButtonsType.YES_NO)
                def response(dialog,result):
                    dialog.destroy()
                    if result==Gtk.ResponseType.YES:self.rectangles.clear();self.close()
                question.connect('response',response);question.present();return True
            self.alive=False;self.doc.close();return False
    return Cropper()



def open_image_layout(app,paths,base_path=None,existing=False,rotation_mode=False,crop_mode=False):
    import io,cairo,pymupdf as fitz,gi
    gi.require_version('Gtk','4.0');gi.require_foreign('cairo')
    from gi.repository import Gtk,Gio,GLib
    from core import images_layout_pdf,editable_pdf_images
    prepared=editable_pdf_images(Path(base_path).read_bytes()) if existing else None
    class Layout(Gtk.Window):
        def __init__(self):
            super().__init__(title=app.tr('image_crop' if crop_mode else 'image_rotate' if rotation_mode else 'image_resize' if existing else 'images_pdf'),transient_for=app.window,modal=True,default_width=850,default_height=800)
            self.base_pdf=prepared[0] if existing else Path(base_path).read_bytes() if base_path else None
            if self.base_pdf:
                with fitz.open(stream=self.base_pdf,filetype='pdf') as doc:
                    if doc.needs_pass:raise ValueError('E_PASSWORD')
                    if not len(doc):raise ValueError('E_INPUT')
                    self.page_sizes=[(p.rect.width,p.rect.height) for p in doc]
            else:self.page_sizes=[(595.,842.)]
            self.image_pages=[0 for _ in paths]
            self.sources=[Path(p).read_bytes() for p in paths];self.layouts=[];self.ratios=[];self.index=0;self.syncing=False;self.running=False;self.valid=True
            for source in self.sources:
                pix=fitz.Pixmap(source);ratio=pix.height/pix.width;self.ratios.append(ratio)
                pw,ph=self.page_sizes[0];w=min(pw*.8,ph*.8/ratio);h=w*ratio;self.layouts.append([pw,ph,(pw-w)/2,(ph-h)/2,w,h])
            if existing:
                self.sources=prepared[1];self.layouts=prepared[2];self.image_pages=prepared[3]
                self.ratios=[v[5]/v[4] for v in self.layouts]
            self.zoom_factor=1.;self.crop_syncing=False;self.crop_spins={}
            self.rotations=[0]*len(self.sources);self.crop_frame=(0.,0.,1.,1.);self.crop_start=None
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);self.set_child(root)
            self.actions=Gio.SimpleActionGroup();self.insert_action_group('layout',self.actions);menu=Gio.Menu()
            for title,entries in [('file',[('save',self.save),('ed_close',self.close)]),('pages',[('ed_previous',lambda:self.navigate(-1)),('ed_next',lambda:self.navigate(1))]),('edit_menu',[('image_left',lambda:self.rotate(90)),('image_right',lambda:self.rotate(-90)),('image_crop_apply',self.apply_crop),('image_crop_reset',self.reset_crop)])]:
                sub=Gio.Menu()
                for key,fn in entries:
                    a=Gio.SimpleAction.new(key,None);a.connect('activate',lambda a,p,fn=fn:fn());self.actions.add_action(a)
                    if not key.startswith('image_crop_') or crop_mode:sub.append(app.tr(key),'layout.'+key)
                menu.append_submenu(app.tr('pdf_pages_menu' if title=='pages' else title),sub)
            bar=Gtk.PopoverMenuBar.new_from_model(menu);root.append(bar);bar.connect('map',lambda *_:compact_menus(bar))
            root.append(Gtk.Label(label=app.tr('image_crop_note' if crop_mode else 'existing_note' if existing else 'layout_note'),wrap=True,xalign=0,margin_start=12,margin_end=12))
            self.controls=Gtk.Grid(column_spacing=8,row_spacing=6,margin_start=12,margin_end=12);root.append(self.controls);self.spins={}
            for n,key in enumerate(('layout_x','layout_y','layout_width')):
                self.controls.attach(Gtk.Label(label=app.tr(key),xalign=0),0,n,1,1)
                spin=Gtk.SpinButton.new_with_range(0,1000,.5);spin.set_digits(2);spin.update_property([Gtk.AccessibleProperty.LABEL],[app.tr(key)])
                self.controls.attach(spin,1,n,1,1);self.spins[key]=spin;spin.connect('value-changed',self.changed)
            self.page_choice=Gtk.DropDown.new_from_strings([str(i+1) for i in range(len(self.page_sizes))])
            self.page_choice.update_property([Gtk.AccessibleProperty.LABEL],[app.tr('existing_page' if existing else 'layout_pdf_page')])
            self.controls.attach(Gtk.Label(label=app.tr('existing_page' if existing else 'layout_pdf_page'),xalign=0),0,3,1,1);self.controls.attach(self.page_choice,1,3,1,1)
            self.page_choice.connect('notify::selected',self.change_page)
            self.zoom=Gtk.DropDown.new_from_strings(['100 %','150 %','200 %','300 %','400 %'])
            self.controls.attach(Gtk.Label(label=app.tr('crop_zoom'),xalign=0),0,4,1,1);self.controls.attach(self.zoom,1,4,1,1)
            self.zoom.connect('notify::selected',lambda w,*_:self.set_zoom([1.,1.5,2.,3.,4.][w.get_selected()]))
            if crop_mode:
                for n,key in enumerate(('crop_left','crop_top','crop_right','crop_bottom')):
                    spin=Gtk.SpinButton.new_with_range(0,2000,.1);spin.set_digits(2);spin.update_property([Gtk.AccessibleProperty.LABEL],[app.tr(key)])
                    self.controls.attach(Gtk.Label(label=app.tr(key),xalign=0),2,n,1,1);self.controls.attach(spin,3,n,1,1)
                    self.crop_spins[key]=spin;spin.connect('value-changed',self.crop_margins_changed)
            self.canvas=Gtk.DrawingArea();self.canvas.set_draw_func(self.draw);scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(self.canvas);root.append(scroll)
            self.selected=True;self.viewed_page=self.image_pages[self.index]
            self.drag_origin=None
            drag=Gtk.GestureDrag();drag.set_button(1)
            drag.connect('drag-begin',self.drag_begin);drag.connect('drag-update',self.drag_update);drag.connect('drag-end',self.drag_end);self.canvas.add_controller(drag)
            self.canvas.update_property([Gtk.AccessibleProperty.LABEL],[app.tr('layout_note')])
            self.status=Gtk.Label(wrap=True,xalign=0,margin_start=12,margin_end=12);root.append(self.status)
            self.connect('close-request',lambda *_:self.running)
            self.refresh();self.present()
        def refresh(self):
            self.syncing=True
            for key,v in zip(self.spins,self.layouts[self.index][2:5]):self.spins[key].set_value(v*25.4/72)
            self.page_choice.set_selected(self.viewed_page if existing else self.image_pages[self.index]);self.syncing=False
            self.actions.lookup_action('ed_previous').set_enabled(self.index>0 and not self.running)
            self.actions.lookup_action('ed_next').set_enabled(self.index<len(self.sources)-1 and not self.running)
            self.sync_crop_spins();self.render()
        def changed(self,*_):
            if self.syncing or self.running or not self.selected:return
            x,y,w=[s.get_value()*72/25.4 for s in self.spins.values()];h=w*self.ratios[self.index]
            pw,ph=self.page_sizes[self.image_pages[self.index]]
            self.layouts[self.index]=[pw,ph,x,y,w,h];self.render()
        def change_page(self,widget,*_):
            if self.syncing or self.running:return
            if existing:
                self.viewed_page=widget.get_selected();self.selected=False;self.drag_origin=None;self.reset_crop();self.refresh();return
            self.image_pages[self.index]=widget.get_selected()
            pw,ph=self.page_sizes[self.image_pages[self.index]];ratio=self.ratios[self.index]
            w=min(self.layouts[self.index][4],pw*.8,ph*.8/ratio);h=w*ratio
            self.layouts[self.index]=[pw,ph,(pw-w)/2,(ph-h)/2,w,h];self.refresh()
        def render(self):
            try:
                data=images_layout_pdf(self.sources,self.layouts,self.base_pdf,self.image_pages if self.base_pdf else None,self.rotations)
                page_number=self.viewed_page if existing else self.image_pages[self.index] if self.base_pdf else self.index
                with fitz.open(stream=data,filetype='pdf') as doc:
                    page=doc[page_number];scale=min(600/page.rect.width,600/page.rect.height)*self.zoom_factor;self.preview_scale=scale;pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                self.surface=cairo.ImageSurface.create_from_png(io.BytesIO(pix.tobytes('png')));self.valid=True
                self.status.set_text(app.tr('layout_status').format(page=self.index+1,total=len(self.sources),name=app.tr('existing_image')+str(self.index+1) if existing else Path(paths[self.index]).name))
            except ValueError:
                self.valid=False;self.status.set_text(app.tr('layout_invalid'))
            self.actions.lookup_action('save').set_enabled(self.valid and not self.running)
            position=self.viewed_page if existing else self.index;total=len(self.page_sizes) if existing else len(self.sources)
            self.actions.lookup_action('ed_next').set_enabled(self.valid and position<total-1 and not self.running)
            self.actions.lookup_action('ed_previous').set_enabled(self.valid and position>0 and not self.running)
            for spin in list(self.spins.values())+list(self.crop_spins.values()):spin.set_sensitive(self.selected and not self.running)
            for key in ('image_left','image_right','image_crop_apply','image_crop_reset'):self.actions.lookup_action(key).set_enabled(self.selected and self.valid and not self.running)
            if existing and not self.selected:self.status.set_text(app.tr('existing_select').format(page=self.viewed_page+1,total=len(self.page_sizes)))
            if self.valid:self.canvas.set_content_width(self.surface.get_width());self.canvas.set_content_height(self.surface.get_height())
            self.canvas.queue_draw()
        def draw(self,area,ctx,width,height):
            ctx.set_source_rgb(.5,.5,.5);ctx.paint()
            if self.valid:
                ctx.set_source_surface(self.surface,0,0);ctx.paint()
                if not self.selected:return
                _,_,x,y,w,h=self.layouts[self.index];scale=self.preview_scale
                ctx.set_source_rgb(.1,.6,1);ctx.set_line_width(2);ctx.set_dash([6,4])
                ctx.rectangle(x*scale,y*scale,w*scale,h*scale);ctx.stroke()
                if crop_mode:
                    x0,y0,x1,y1=self.crop_frame
                    ctx.set_source_rgba(0,0,0,.55)
                    for rx,ry,rw,rh in ((x,y,w,h*y0),(x,y+h*y1,w,h*(1-y1)),(x,y+h*y0,w*x0,h*(y1-y0)),(x+w*x1,y+h*y0,w*(1-x1),h*(y1-y0))):
                        ctx.rectangle(rx*scale,ry*scale,rw*scale,rh*scale);ctx.fill()
                    ctx.set_source_rgb(.2,.9,.3);ctx.rectangle((x+w*x0)*scale,(y+h*y0)*scale,w*(x1-x0)*scale,h*(y1-y0)*scale);ctx.stroke()
                    ctx.set_dash([])
                    for fx,fy in ((x0,y0),(x1,y0),(x0,y1),(x1,y1),((x0+x1)/2,y0),((x0+x1)/2,y1),(x0,(y0+y1)/2),(x1,(y0+y1)/2)):
                        ctx.rectangle((x+w*fx)*scale-4,(y+h*fy)*scale-4,8,8);ctx.fill()
                    return
                ctx.set_dash([])
                for cx,cy in ((x,y),(x+w,y),(x,y+h),(x+w,y+h)):
                    ctx.rectangle(cx*scale-5,cy*scale-5,10,10)
                    ctx.set_source_rgb(1,1,1);ctx.fill_preserve();ctx.set_source_rgb(.1,.6,1);ctx.stroke()
        def drag_begin(self,gesture,x,y):
            self.drag_origin=None;self.resize_corner=None
            if self.running or not self.valid:return
            if existing:
                found=False
                for i,layout in reversed(list(enumerate(self.layouts))):
                    _,_,ix,iy,iw,ih=layout
                    if self.image_pages[i]==self.viewed_page and ix-8/self.preview_scale<=x/self.preview_scale<=ix+iw+8/self.preview_scale and iy-8/self.preview_scale<=y/self.preview_scale<=iy+ih+8/self.preview_scale:
                        if i!=self.index:self.crop_frame=(0.,0.,1.,1.)
                        self.index=i;self.selected=True;found=True;self.refresh();break
                if not found:self.selected=False;self.refresh();return
            else:
                _,_,ix,iy,iw,ih=self.layouts[self.index]
                self.selected=(ix-8/self.preview_scale<=x/self.preview_scale<=ix+iw+8/self.preview_scale and iy-8/self.preview_scale<=y/self.preview_scale<=iy+ih+8/self.preview_scale)
                self.refresh()
                if not self.selected:return
            _,_,left,top,w,h=self.layouts[self.index];scale=self.preview_scale
            if crop_mode:
                px=max(0,min(1,(x/scale-left)/w));py=max(0,min(1,(y/scale-top)/h))
                self.crop_start=(px,py);self.crop_original=self.crop_frame;self.crop_handle='new'
                x0,y0,x1,y1=self.crop_frame
                if self.crop_frame!=(0.,0.,1.,1.):
                    for name,hx,hy in (('lt',x0,y0),('rt',x1,y0),('lb',x0,y1),('rb',x1,y1),('t',(x0+x1)/2,y0),('b',(x0+x1)/2,y1),('l',x0,(y0+y1)/2),('r',x1,(y0+y1)/2)):
                        if abs(px-hx)*w*scale<=9 and abs(py-hy)*h*scale<=9:self.crop_handle=name;break
                    else:
                        if x0<px<x1 and y0<py<y1:self.crop_handle='move'
                self.drag_origin=(left,top);return
            for sx,sy,cx,cy in ((-1,-1,left,top),(1,-1,left+w,top),(-1,1,left,top+h),(1,1,left+w,top+h)):
                if abs(x-cx*scale)<=8 and abs(y-cy*scale)<=8:
                    self.drag_origin=(left,top);self.resize_corner=(sx,sy,w,h)
                    self.canvas.set_cursor_from_name('nwse-resize' if sx==sy else 'nesw-resize');return
            if left<=x/scale<=left+w and top<=y/scale<=top+h:
                self.drag_origin=(left,top);self.canvas.set_cursor_from_name('grabbing')
        def drag_update(self,gesture,dx,dy):
            if self.drag_origin is None or self.running:return
            pw,ph,_,_,w,h=self.layouts[self.index];left,top=self.drag_origin
            if crop_mode:
                ddx=dx/self.preview_scale/w;ddy=dy/self.preview_scale/h;x0,y0,x1,y1=self.crop_original
                if self.crop_handle=='new':
                    x0,y0=self.crop_start;x1=max(0,min(1,x0+ddx));y1=max(0,min(1,y0+ddy))
                    if abs(x1-x0)>.005 and abs(y1-y0)>.005:self.crop_frame=(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
                elif self.crop_handle=='move':
                    ddx=max(-x0,min(1-x1,ddx));ddy=max(-y0,min(1-y1,ddy));self.crop_frame=(x0+ddx,y0+ddy,x1+ddx,y1+ddy)
                else:
                    if 'l' in self.crop_handle:x0=max(0,min(x1-.005,x0+ddx))
                    if 'r' in self.crop_handle:x1=min(1,max(x0+.005,x1+ddx))
                    if 't' in self.crop_handle:y0=max(0,min(y1-.005,y0+ddy))
                    if 'b' in self.crop_handle:y1=min(1,max(y0+.005,y1+ddy))
                    self.crop_frame=(x0,y0,x1,y1)
                self.sync_crop_spins();self.canvas.queue_draw();return
            if self.resize_corner:
                sx,sy,start_w,start_h=self.resize_corner;ratio=start_h/start_w
                anchor_x=left+(start_w if sx<0 else 0);anchor_y=top+(start_h if sy<0 else 0)
                change=(sx*dx/self.preview_scale+sy*dy/self.preview_scale*ratio)/(1+ratio*ratio)
                limit=min(anchor_x if sx<0 else pw-anchor_x,(anchor_y if sy<0 else ph-anchor_y)/ratio)
                w=max(min(4.,limit),min(limit,start_w+change));h=w*ratio
                self.layouts[self.index][2:]=[anchor_x-w if sx<0 else anchor_x,anchor_y-h if sy<0 else anchor_y,w,h]
            else:
                self.layouts[self.index][2]=max(0,min(pw-w,left+dx/self.preview_scale))
                self.layouts[self.index][3]=max(0,min(ph-h,top+dy/self.preview_scale))
            self.refresh()
        def drag_end(self,gesture,dx,dy):
            self.drag_update(gesture,dx,dy);self.drag_origin=None;self.canvas.set_cursor_from_name('default')
        def set_zoom(self,value):
            if self.running:return
            self.zoom_factor=value;self.render()
        def sync_crop_spins(self):
            if not crop_mode:return
            self.crop_syncing=True;x0,y0,x1,y1=self.crop_frame;w,h=self.layouts[self.index][4:];mm=25.4/72
            for spin,value in zip(self.crop_spins.values(),(x0*w,y0*h,(1-x1)*w,(1-y1)*h)):spin.set_value(value*mm)
            self.crop_syncing=False
        def crop_margins_changed(self,*_):
            if self.crop_syncing or self.running or not self.selected:return
            w,h=self.layouts[self.index][4:];l,t,r,b=[spin.get_value()*72/25.4 for spin in self.crop_spins.values()]
            if l+r>=w or t+b>=h:
                self.sync_crop_spins();return
            self.crop_frame=(l/w,t/h,1-r/w,1-b/h);self.canvas.queue_draw()
        def reset_crop(self):
            self.crop_frame=(0.,0.,1.,1.);self.sync_crop_spins();self.canvas.queue_draw()
        def apply_crop(self):
            if not crop_mode or not self.selected or self.running or self.crop_frame==(0.,0.,1.,1.):return
            from core import crop_embedded_image
            pw,ph,x,y,w,h=self.layouts[self.index];x0,y0,x1,y1=self.crop_frame
            try:data=crop_embedded_image(self.sources[self.index],self.crop_frame,self.rotations[self.index])
            except Exception as exc:app.error(exc);return
            self.sources[self.index]=data;self.layouts[self.index]=[pw,ph,x+w*x0,y+h*y0,w*(x1-x0),h*(y1-y0)]
            self.rotations[self.index]=0;self.ratios[self.index]=self.layouts[self.index][5]/self.layouts[self.index][4];self.reset_crop();self.refresh()
        def rotate(self,angle):
            if not self.selected or self.running or not self.valid:return
            pw,ph,x,y,w,h=self.layouts[self.index]
            new_w,new_h=h,w
            if new_w>pw or new_h>ph:
                app.message('image_rotate',app.tr('image_rotate_fit'));return
            self.layouts[self.index]=[pw,ph,max(0,min(pw-new_w,x+(w-new_w)/2)),max(0,min(ph-new_h,y+(h-new_h)/2)),new_w,new_h]
            self.rotations[self.index]=(self.rotations[self.index]+angle)%360;self.ratios[self.index]=new_h/new_w;self.refresh()
        def navigate(self,delta):
            if self.valid and not self.running:
                if existing:
                    self.viewed_page=max(0,min(len(self.page_sizes)-1,self.viewed_page+delta));self.selected=False;self.drag_origin=None;self.reset_crop()
                else:self.index=max(0,min(len(self.sources)-1,self.index+delta));self.selected=True
                self.refresh()
        def save(self):
            if crop_mode:self.apply_crop()
            if self.valid and not self.running:self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('images_pdf',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            if self.running or not self.valid:return
            self.running=True;self.controls.set_sensitive(False);self.render();app.busy=True;app.apply_function_states(app.function_states)
            def worker():
                try:process('images_pdf',[base_path] if existing else paths,target,{'placements':[list(v) for v in self.layouts],'image_sources':self.sources,'base_pdf':self.base_pdf,'image_pages':self.image_pages,'image_rotations':self.rotations});error=None
                except Exception as exc:error=exc
                def finish():
                    self.running=False;app.busy=False;app.apply_function_states(app.function_states);app.check_tools()
                    if error:self.controls.set_sensitive(True);self.render();app.error(error)
                    else:self.close();app.message('done',app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
    return Layout()


def open_image_extractor(app,path):
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gio,GLib,Gdk
    from core import pdf_image_choices
    class Extractor(Gtk.Window):
        def __init__(self):
            super().__init__(title=app.tr('extract_images'),transient_for=app.window,modal=True,default_width=850,default_height=700)
            self.source=Path(path).read_bytes();self.alive=True;self.running=False;self.loading=True;self.checks={}
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.set_child(root)
            self.actions=Gio.SimpleActionGroup();self.insert_action_group('extractor',self.actions);menu=Gio.Menu()
            for title,entries in [('file',[('save',self.save),('ed_close',self.close)]),('edit_menu',[('extract_all',lambda:self.select(True)),('extract_none',lambda:self.select(False))])]:
                sub=Gio.Menu()
                for key,fn in entries:
                    action=Gio.SimpleAction.new(key,None);action.connect('activate',lambda a,p,fn=fn:fn());self.actions.add_action(action);sub.append(app.tr(key),'extractor.'+key)
                menu.append_submenu(app.tr(title),sub)
            bar=Gtk.PopoverMenuBar.new_from_model(menu);root.append(bar);bar.connect('map',lambda *_:compact_menus(bar))
            root.append(Gtk.Label(label=app.tr('extract_note'),wrap=True,xalign=0,margin_start=12,margin_end=12))
            self.flow=Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,homogeneous=True,max_children_per_line=3,min_children_per_line=1,column_spacing=12,row_spacing=12,margin_start=12,margin_end=12)
            scroll=Gtk.ScrolledWindow(vexpand=True);scroll.set_child(self.flow);root.append(scroll)
            self.status=Gtk.Label(label=app.tr('working'),wrap=True,xalign=0,margin_start=12,margin_end=12,margin_bottom=12);root.append(self.status)
            self.connect('close-request',self.closing);self.update();self.present()
            def worker():
                try:items=pdf_image_choices(self.source);error=None
                except Exception as exc:items=[];error=exc
                GLib.idle_add(self.loaded,items,error)
            threading.Thread(target=worker,daemon=True).start()
        def loaded(self,items,error):
            if not self.alive:return False
            self.loading=False
            if error:self.close();app.error(error);return False
            self.items=items
            for item in items:
                box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
                picture=Gtk.Picture.new_for_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(item['preview'])))
                picture.set_size_request(180,135);picture.set_can_shrink(True);box.append(picture)
                label=app.tr('extract_item').format(pages=', '.join(map(str,item['pages'])),width=item['width'],height=item['height'],ext=item['ext'].upper())
                check=Gtk.CheckButton();check.set_child(Gtk.Label(label=label,wrap=True,xalign=0));check.update_property([Gtk.AccessibleProperty.LABEL],[label]);check.connect('toggled',lambda *_:self.update());box.append(check)
                self.checks[item['xref']]=check;self.flow.insert(box,-1)
            self.update();return False
        def update(self):
            count=sum(check.get_active() for check in self.checks.values())
            self.actions.lookup_action('save').set_enabled(bool(count) and not self.running and not self.loading)
            for key in ('extract_all','extract_none'):self.actions.lookup_action(key).set_enabled(bool(self.checks) and not self.running)
            if not self.loading:self.status.set_text(app.tr('extract_count').format(count=count,total=len(self.checks)))
        def select(self,value):
            if not self.running:
                for check in self.checks.values():check.set_active(value)
        def save(self):
            if not self.running and any(c.get_active() for c in self.checks.values()):
                self.picker=select_save_target(self,app.tr('extract_save'),output_suggestion('extract_images',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            chosen=[xref for xref,check in self.checks.items() if check.get_active()]
            if self.running or not chosen:return
            self.running=True;self.flow.set_sensitive(False);self.update();self.status.set_text(app.tr('working'));app.busy=True;app.apply_function_states(app.function_states)
            def worker():
                try:process('extract_images',[path],target,{'image_xrefs':chosen,'source_pdf':self.source});error=None
                except Exception as exc:error=exc
                def finish():
                    self.running=False;app.busy=False;app.apply_function_states(app.function_states);app.check_tools()
                    if error:self.flow.set_sensitive(True);self.update();app.error(error)
                    else:self.close();app.message('done',app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False;return False
    return Extractor()



def open_text_search(app,path):
    import gi,pymupdf as fitz
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import search_pdf_text
    class Search(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not len(doc):raise ValueError('E_INPUT')
            super().__init__(title=app.tr('text_search')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1000,default_height=800)
            self.alive=True;self.generation=0;self.results=[];self.current=0
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);self.set_child(root)
            root.append(Gtk.Label(label=app.tr('search_pdf_note'),wrap=True,xalign=0,margin_start=12,margin_end=12))
            self.entry=Gtk.SearchEntry(placeholder_text=app.tr('search_pdf_query'));self.entry.update_property([Gtk.AccessibleProperty.LABEL],[app.tr('search_pdf_query')]);root.append(self.entry)
            self.entry.connect('activate',lambda *_:self.search());self.entry.connect('search-changed',lambda *_:self.search())
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL,vexpand=True);root.append(pane)
            self.pane=pane;pane.set_position(330)
            pane.set_resize_start_child(True);pane.set_resize_end_child(True)
            pane.set_shrink_start_child(False);pane.set_shrink_end_child(False)
            self.list=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE);self.list.connect('row-selected',self.selected)
            left=Gtk.ScrolledWindow(min_content_width=190);left.set_child(self.list);pane.set_start_child(left)
            self.picture=Gtk.Picture();self.picture.set_can_shrink(False);right=Gtk.ScrolledWindow();right.set_child(self.picture);pane.set_end_child(right)
            self.status=Gtk.Label(wrap=True,xalign=0,margin_start=12,margin_end=12,margin_bottom=10);root.append(self.status)
            self.connect('close-request',self.closing);self.show_page(0,[]);self.present();self.entry.grab_focus()
        def search(self):
            self.generation+=1;generation=self.generation;query=self.entry.get_text().strip()
            while (row:=self.list.get_first_child()) is not None:self.list.remove(row)
            self.results=[]
            if not query:self.status.set_text(app.tr('search_pdf_query'));self.show_page(0,[]);return
            self.status.set_text(app.tr('working'))
            def worker():
                try:results=search_pdf_text(self.source,query);error=None
                except Exception as exc:results=[];error=exc
                def finish():
                    if not self.alive or generation!=self.generation:return False
                    if error:app.error(error);self.status.set_text(app.tr('E_INPUT'));return False
                    self.results=results
                    for result in results:
                        self.list.append(Gtk.Label(label=app.tr('search_pdf_page').format(page=result['page']+1,count=len(result['rects'])),xalign=0,margin_start=10,margin_end=10,margin_top=10,margin_bottom=10))
                    self.status.set_text(app.tr('search_pdf_count').format(count=sum(len(r['rects']) for r in results),pages=len(results)) if results else app.tr('search_pdf_none'))
                    if results:self.list.select_row(self.list.get_row_at_index(0))
                    else:self.show_page(0,[])
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def selected(self,box,row):
            if row is not None and row.get_index()<len(self.results):
                result=self.results[row.get_index()];self.show_page(result['page'],result['rects'])
        def show_page(self,number,rects):
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                page=doc[number]
                for rect in rects:
                    mark=page.add_highlight_annot(fitz.Rect(rect));mark.set_colors(stroke=(1,.8,0));mark.update()
                pix=page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False)
            self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))))
        def closing(self,*_):self.alive=False;self.generation+=1;return False
    return Search()

def open_watermark(app,path):
    import gi,pymupdf as fitz
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import apply_watermark
    class Watermark(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                count=len(doc)
            super().__init__(title=app.tr('watermark')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1100,default_height=850)
            self.running=False;self.pending=0;self.alive=True
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);pane.set_position(330);self.set_child(pane)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=16,margin_end=16,margin_top=16,margin_bottom=16)
            scroll=Gtk.ScrolledWindow(min_content_width=290);scroll.set_child(self.controls);pane.set_start_child(scroll)
            self.controls.append(Gtk.Label(label=app.tr('watermark_note'),wrap=True,xalign=0,max_width_chars=32))
            self.controls.append(Gtk.Label(label=app.tr('text'),xalign=0));self.text=Gtk.Entry();self.controls.append(self.text)
            self.fields={}
            for key,value,lower,upper in [('watermark_angle',45,-90,90),('watermark_size',72,8,200),('watermark_opacity',20,1,100)]:
                self.controls.append(Gtk.Label(label=app.tr(key),xalign=0))
                spin=Gtk.SpinButton.new_with_range(lower,upper,1);spin.set_value(value);self.fields[key]=spin;self.controls.append(spin)
                spin.connect('value-changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_color'),xalign=0))
            self.color=Gtk.DropDown.new_from_strings([app.tr('watermark_'+c) for c in ('gray','red','blue')]);self.controls.append(self.color);self.color.connect('notify::selected',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_preview_page'),xalign=0));self.page=Gtk.SpinButton.new_with_range(1,count,1);self.page.set_value(1);self.controls.append(self.page);self.page.connect('value-changed',self.schedule)
            self.save_button=Gtk.Button(label=app.tr('save_as'));self.save_button.add_css_class('suggested-action');self.controls.append(self.save_button);self.save_button.connect('clicked',self.save)
            self.status=Gtk.Label(wrap=True,xalign=0);self.controls.append(self.status)
            self.picture=Gtk.Picture();self.picture.set_can_shrink(True)
            preview=Gtk.ScrolledWindow(hexpand=True,vexpand=True);preview.set_child(self.picture);pane.set_end_child(preview)
            self.text.connect('changed',self.schedule);self.connect('close-request',self.closing)
            self.render();self.present();self.text.grab_focus()
        def options(self):
            return dict(text=self.text.get_text().strip(),watermark_color=('gray','red','blue')[self.color.get_selected()],**{key:spin.get_value() for key,spin in self.fields.items()})
        def schedule(self,*_):
            if self.pending:GLib.source_remove(self.pending)
            self.pending=GLib.timeout_add(120,self.render)
        def render(self):
            self.pending=0
            if not self.alive:return False
            opts=self.options();self.save_button.set_sensitive(bool(opts['text']) and not self.running)
            try:
                with fitz.open(stream=self.source,filetype='pdf') as doc:
                    page=doc[int(self.page.get_value())-1]
                    if opts['text']:apply_watermark(page,opts['text'],opts)
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False)
                self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))));self.status.set_text('')
            except Exception as exc:self.status.set_text(app.tr(str(exc)));self.save_button.set_sensitive(False)
            return False
        def save(self,*_):
            if self.running or not self.options()['text']:return
            self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('watermark',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=self.options();self.running=True;self.controls.set_sensitive(False);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    with fitz.open(stream=self.source,filetype='pdf') as doc:
                        for page in doc:apply_watermark(page,opts['text'],opts)
                        data=doc.tobytes(garbage=4,deflate=True)
                    # Never overwrite an existing file, including the source.
                    with destination.open('xb') as output:output.write(data)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:self.status.set_text('');app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False
            if self.pending:GLib.source_remove(self.pending);self.pending=0
            return False
    return Watermark()

def open_page_numbers(app,path):
    import gi,pymupdf as fitz
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import apply_page_number
    class Watermark(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                count=len(doc)
            super().__init__(title=app.tr('numbers')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1100,default_height=850)
            self.running=False;self.pending=0;self.alive=True
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);pane.set_position(330);self.set_child(pane)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=16,margin_end=16,margin_top=16,margin_bottom=16)
            scroll=Gtk.ScrolledWindow(min_content_width=290);scroll.set_child(self.controls);pane.set_start_child(scroll)
            self.controls.append(Gtk.Label(label=app.tr('number_note'),wrap=True,xalign=0,max_width_chars=32))
            self.controls.append(Gtk.Label(label=app.tr('text'),xalign=0));self.text=Gtk.Entry(text='Seite ##');self.controls.append(self.text)
            self.fields={}
            for key,value,lower,upper in [('number_x',50,0,100),('number_y',95,0,100),('number_size',12,8,100),('number_start',1,0,999999)]:
                self.controls.append(Gtk.Label(label=app.tr(key),xalign=0))
                spin=Gtk.SpinButton.new_with_range(lower,upper,1);spin.set_value(value);self.fields[key]=spin;self.controls.append(spin)
                spin.connect('value-changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_preview_page'),xalign=0));self.page=Gtk.SpinButton.new_with_range(1,count,1);self.page.set_value(1);self.controls.append(self.page);self.page.connect('value-changed',self.schedule)
            self.save_button=Gtk.Button(label=app.tr('save_as'));self.save_button.add_css_class('suggested-action');self.controls.append(self.save_button);self.save_button.connect('clicked',self.save)
            self.status=Gtk.Label(wrap=True,xalign=0);self.controls.append(self.status)
            self.picture=Gtk.Picture();self.picture.set_can_shrink(True)
            preview=Gtk.ScrolledWindow(hexpand=True,vexpand=True);preview.set_child(self.picture);pane.set_end_child(preview)
            self.text.connect('changed',self.schedule);self.connect('close-request',self.closing)
            self.render();self.present();self.text.grab_focus()
        def options(self):
            return dict(text=self.text.get_text().strip(),**{key:spin.get_value() for key,spin in self.fields.items()})
        def schedule(self,*_):
            if self.pending:GLib.source_remove(self.pending)
            self.pending=GLib.timeout_add(120,self.render)
        def render(self):
            self.pending=0
            if not self.alive:return False
            opts=self.options();self.save_button.set_sensitive(bool(opts['text']) and not self.running)
            try:
                with fitz.open(stream=self.source,filetype='pdf') as doc:
                    page=doc[int(self.page.get_value())-1]
                    if opts['text']:apply_page_number(page,int(self.page.get_value())-1,opts)
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False)
                self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))));self.status.set_text('')
            except Exception as exc:self.status.set_text(app.tr(str(exc)));self.save_button.set_sensitive(False)
            return False
        def save(self,*_):
            if self.running or not self.options()['text']:return
            self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('numbers',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=self.options();self.running=True;self.controls.set_sensitive(False);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    with fitz.open(stream=self.source,filetype='pdf') as doc:
                        for index,page in enumerate(doc):apply_page_number(page,index,opts)
                        data=doc.tobytes(garbage=4,deflate=True)
                    # Never overwrite an existing file, including the source.
                    with destination.open('xb') as output:output.write(data)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:self.status.set_text('');app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False
            if self.pending:GLib.source_remove(self.pending);self.pending=0
            return False
    return Watermark()

def open_annotations(app,path):
    import gi,pymupdf as fitz
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import apply_annotation
    class Watermark(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                count=len(doc)
            super().__init__(title=app.tr('annotations')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1100,default_height=850)
            self.running=False;self.pending=0;self.alive=True
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);pane.set_position(330);self.set_child(pane)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=16,margin_end=16,margin_top=16,margin_bottom=16)
            scroll=Gtk.ScrolledWindow(min_content_width=290);scroll.set_child(self.controls);pane.set_start_child(scroll)
            self.controls.append(Gtk.Label(label=app.tr('annotation_note'),wrap=True,xalign=0,max_width_chars=32))
            self.controls.append(Gtk.Label(label=app.tr('text'),xalign=0));self.text=Gtk.Entry();self.controls.append(self.text)
            self.fields={}
            for key,value,lower,upper in [('note_x',10,0,100),('note_y',10,0,100)]:
                self.controls.append(Gtk.Label(label=app.tr(key),xalign=0))
                spin=Gtk.SpinButton.new_with_range(lower,upper,1);spin.set_value(value);self.fields[key]=spin;self.controls.append(spin)
                spin.connect('value-changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_preview_page'),xalign=0));self.page=Gtk.SpinButton.new_with_range(1,count,1);self.page.set_value(1);self.controls.append(self.page);self.page.connect('value-changed',self.schedule)
            self.save_button=Gtk.Button(label=app.tr('save_as'));self.save_button.add_css_class('suggested-action');self.controls.append(self.save_button);self.save_button.connect('clicked',self.save)
            self.status=Gtk.Label(wrap=True,xalign=0);self.controls.append(self.status)
            self.picture=Gtk.Picture();self.picture.set_can_shrink(True)
            preview=Gtk.ScrolledWindow(hexpand=True,vexpand=True);preview.set_child(self.picture);pane.set_end_child(preview)
            self.picture.set_cursor_from_name('crosshair')
            self.drag=Gtk.GestureDrag.new();self.drag.set_button(1)
            self.drag.connect('drag-begin',self.drag_begin);self.drag.connect('drag-update',self.drag_update)
            self.picture.add_controller(self.drag)
            self.text.connect('changed',self.schedule);self.connect('close-request',self.closing)
            self.render();self.present();self.text.grab_focus()
        def page_bounds(self):
            paint=self.picture.get_paintable()
            if paint is None:return None
            width=self.picture.get_width();height=self.picture.get_height()
            pw=paint.get_intrinsic_width();ph=paint.get_intrinsic_height()
            if min(width,height,pw,ph)<=0:return None
            scale=min(width/pw,height/ph);w=pw*scale;h=ph*scale
            return ((width-w)/2,(height-h)/2,w,h)
        def position_at(self,x,y,clamp=False):
            if self.running:return False
            bounds=self.page_bounds()
            if not bounds:return False
            left,top,width,height=bounds
            if not clamp and not (left<=x<=left+width and top<=y<=top+height):return False
            self.fields['note_x'].set_value(max(0,min(100,(x-left)/width*100)))
            self.fields['note_y'].set_value(max(0,min(100,(y-top)/height*100)))
            return True
        def drag_begin(self,gesture,x,y):
            self.drag_origin=(x,y) if self.position_at(x,y) else None
        def drag_update(self,gesture,dx,dy):
            if self.drag_origin:
                x,y=self.drag_origin;self.position_at(x+dx,y+dy,clamp=True)
        def options(self):
            return dict(note_page=int(self.page.get_value())-1,text=self.text.get_text().strip(),**{key:spin.get_value() for key,spin in self.fields.items()})
        def schedule(self,*_):
            if self.pending:GLib.source_remove(self.pending)
            self.pending=GLib.timeout_add(120,self.render)
        def render(self):
            self.pending=0
            if not self.alive:return False
            opts=self.options();self.save_button.set_sensitive(bool(opts['text']) and not self.running)
            try:
                with fitz.open(stream=self.source,filetype='pdf') as doc:
                    page=doc[int(self.page.get_value())-1]
                    if opts['text']:apply_annotation(page,opts['text'],opts)
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False)
                self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))));self.status.set_text('')
            except Exception as exc:self.status.set_text(app.tr(str(exc)));self.save_button.set_sensitive(False)
            return False
        def save(self,*_):
            if self.running or not self.options()['text']:return
            self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('annotations',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=self.options();self.running=True;self.controls.set_sensitive(False);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    with fitz.open(stream=self.source,filetype='pdf') as doc:
                        apply_annotation(doc[opts['note_page']],opts['text'],opts)
                        data=doc.tobytes(garbage=4,deflate=True)
                    # Never overwrite an existing file, including the source.
                    with destination.open('xb') as output:output.write(data)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:self.status.set_text('');app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False
            if self.pending:GLib.source_remove(self.pending);self.pending=0
            return False
    return Watermark()

def open_signature(app,path):
    import gi,pymupdf as fitz
    gi.require_foreign('cairo')
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import apply_signature
    class Watermark(Gtk.Window):
        def __init__(self):
            self.source=Path(path).read_bytes()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                count=len(doc)
            super().__init__(title=app.tr('images_pdf')+' — '+Path(path).name,transient_for=app.window,modal=True,default_width=1100,default_height=850)
            self.running=False;self.pending=0;self.alive=True
            pane=Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL);pane.set_position(330);self.set_child(pane)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=16,margin_end=16,margin_top=16,margin_bottom=16)
            scroll=Gtk.ScrolledWindow(min_content_width=290);scroll.set_child(self.controls);pane.set_start_child(scroll)
            self.controls.append(Gtk.Label(label=app.tr('signature_note'),wrap=True,xalign=0,max_width_chars=32))
            self.selected=True;self.resize_origin=None
            self.signature=None
            self.preview_doc=fitz.open(stream=self.source,filetype='pdf')
            self.text=Gtk.Entry()
            choose=Gtk.Button(label=app.tr('signature_choose'));self.controls.append(choose)
            def picked(paths):
                try:
                    data=Path(paths[0]).read_bytes();fitz.Pixmap(data)
                    self.signature=data;self.text.set_text(Path(paths[0]).name);self.schedule()
                except Exception as exc:app.error(exc)
            choose.connect('clicked',lambda *_:app.choose_files(parent=self,on_selected=picked,tool='images_pdf',selection_title=app.tr('signature_choose')))
            self.text.set_editable(False);self.controls.append(self.text)
            self.fields={}
            for key,value,lower,upper in [('signature_x',10,0,100),('signature_y',75,0,100),('signature_width',25,1,100)]:
                self.controls.append(Gtk.Label(label=app.tr(key),xalign=0))
                spin=Gtk.SpinButton.new_with_range(lower,upper,1);spin.set_value(value);self.fields[key]=spin;self.controls.append(spin)
                spin.connect('value-changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_preview_page'),xalign=0));self.page=Gtk.SpinButton.new_with_range(1,count,1);self.page.set_value(1);self.controls.append(self.page);self.page.connect('value-changed',self.schedule)
            self.save_button=Gtk.Button(label=app.tr('save_as'));self.save_button.add_css_class('suggested-action');self.controls.append(self.save_button);self.save_button.connect('clicked',self.save)
            self.status=Gtk.Label(wrap=True,xalign=0);self.controls.append(self.status)
            self.picture=Gtk.Picture();self.picture.set_can_shrink(True)
            overlay=Gtk.Overlay();overlay.set_child(self.picture)
            self.selection=Gtk.DrawingArea(hexpand=True,vexpand=True);self.selection.set_can_target(False)
            self.selection.set_draw_func(self.draw_selection);overlay.add_overlay(self.selection)
            preview=Gtk.ScrolledWindow(hexpand=True,vexpand=True);preview.set_child(overlay);pane.set_end_child(preview)
            self.picture.set_cursor_from_name('crosshair')
            self.drag=Gtk.GestureDrag.new();self.drag.set_button(1)
            self.drag.connect('drag-begin',self.drag_begin);self.drag.connect('drag-update',self.drag_update);self.drag.connect('drag-end',self.drag_end)
            self.picture.add_controller(self.drag)
            self.text.connect('changed',self.schedule);self.connect('close-request',self.closing)
            self.render();self.present();self.text.grab_focus()
        def page_bounds(self):
            paint=self.picture.get_paintable()
            if paint is None:return None
            width=self.picture.get_width();height=self.picture.get_height()
            pw=paint.get_intrinsic_width();ph=paint.get_intrinsic_height()
            if min(width,height,pw,ph)<=0:return None
            scale=min(width/pw,height/ph);w=pw*scale;h=ph*scale
            return ((width-w)/2,(height-h)/2,w,h)
        def position_at(self,x,y,clamp=False):
            if self.running:return False
            bounds=self.page_bounds()
            if not bounds:return False
            left,top,width,height=bounds
            if not clamp and not (left<=x<=left+width and top<=y<=top+height):return False
            self.fields['signature_x'].set_value(max(0,min(100,(x-left)/width*100)))
            self.fields['signature_y'].set_value(max(0,min(100,(y-top)/height*100)))
            return True
        def signature_bounds(self):
            if not self.signature:return None
            bounds=self.page_bounds()
            if not bounds:return
            left,top,width,height=bounds
            opts=self.options()
            with fitz.open(stream=self.source,filetype='pdf') as doc:
                page=doc[opts['note_page']]
                image=fitz.Pixmap(self.signature)
                w=opts['signature_width']/100*page.rect.width;h=w*image.height/image.width
                scale=min(1,(page.rect.height-8)/h);w*=scale;h*=scale
                px=min(page.rect.width-w-4,max(4,opts['signature_x']/100*page.rect.width))
                py=min(page.rect.height-h-4,max(4,opts['signature_y']/100*page.rect.height))
                sx=left+px/page.rect.width*width;sy=top+py/page.rect.height*height
                sw=w/page.rect.width*width;sh=h/page.rect.height*height
            return sx,sy,sw,sh
        def draw_selection(self,area,ctx,width,height):
            rect=self.signature_bounds()
            if not rect or not self.selected:return
            x,y,w,h=rect
            ctx.set_source_rgb(.12,.55,.9);ctx.set_line_width(2);ctx.rectangle(x,y,w,h);ctx.stroke()
            for px,py in ((x,y),(x+w,y),(x,y+h),(x+w,y+h)):
                ctx.set_source_rgb(1,1,1);ctx.rectangle(px-5,py-5,10,10);ctx.fill_preserve()
                ctx.set_source_rgb(.12,.55,.9);ctx.stroke()
        def drag_begin(self,gesture,x,y):
            self.drag_origin=None;self.resize_origin=None
            if self.running or not self.signature:return
            rect=self.signature_bounds()
            if not rect:return
            sx,sy,sw,sh=rect
            if self.selected:
                for cx,cy,signx,signy in ((sx,sy,-1,-1),(sx+sw,sy,1,-1),(sx,sy+sh,-1,1),(sx+sw,sy+sh,1,1)):
                    if abs(x-cx)<=10 and abs(y-cy)<=10:
                        self.resize_origin=(sx,sy,sw,sh,signx,signy,self.fields['signature_width'].get_value())
                        self.picture.set_cursor_from_name('nwse-resize' if signx==signy else 'nesw-resize');return
            if sx<=x<=sx+sw and sy<=y<=sy+sh:
                self.selected=True;self.drag_origin=(sx,sy);self.picture.set_cursor_from_name('grabbing')
            else:self.selected=False
            self.selection.queue_draw()
        def drag_update(self,gesture,dx,dy):
            if self.resize_origin:
                x,y,w,h,sx,sy,percent=self.resize_origin
                factor=max(.04,1+(dx*sx*w+dy*sy*h)/(w*w+h*h))
                new_percent=max(1,min(100,percent*factor));factor=new_percent/percent
                self.fields['signature_width'].set_value(new_percent)
                self.position_at(x if sx>0 else x+w-w*factor,y if sy>0 else y+h-h*factor,clamp=True)
            elif self.drag_origin:
                x,y=self.drag_origin;self.position_at(x+dx,y+dy,clamp=True)
        def drag_end(self,*_):
            self.drag_origin=None;self.resize_origin=None;self.picture.set_cursor_from_name('grab')
            if self.pending:GLib.source_remove(self.pending);self.pending=0
            self.render()
        def options(self):
            return dict(signature_bytes=self.signature,note_page=int(self.page.get_value())-1,text=self.text.get_text().strip(),**{key:spin.get_value() for key,spin in self.fields.items()})
        def schedule(self,*_):
            if not self.pending:self.pending=GLib.timeout_add(33,self.render)
        def render(self):
            self.pending=0
            if not self.alive:return False
            opts=self.options();self.save_button.set_sensitive(bool(opts['text']) and not self.running)
            try:
                with fitz.open() as doc:
                    number=int(self.page.get_value())-1
                    doc.insert_pdf(self.preview_doc,from_page=number,to_page=number)
                    page=doc[0]
                    if self.signature:apply_signature(page,self.signature,opts)
                    pix=page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
                self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))));self.selection.queue_draw();self.status.set_text('')
            except Exception as exc:self.status.set_text(app.tr(str(exc)));self.save_button.set_sensitive(False)
            return False
        def save(self,*_):
            if self.running or not self.options()['text']:return
            self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('signature_image',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=self.options();self.running=True;self.controls.set_sensitive(False);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    with fitz.open(stream=self.source,filetype='pdf') as doc:
                        apply_signature(doc[opts['note_page']],opts['signature_bytes'],opts)
                        data=doc.tobytes(garbage=4,deflate=True)
                    # Never overwrite an existing file, including the source.
                    with destination.open('xb') as output:output.write(data)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:self.status.set_text('');app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False;self.preview_doc.close()
            if self.pending:GLib.source_remove(self.pending);self.pending=0
            return False
    return Watermark()

def open_overlay(app,paths=None):
    import gi,pymupdf as fitz
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,Gdk,GLib
    from core import overlay_documents
    class Overlay(Gtk.Window):
        def __init__(self):
            super().__init__(title=app.tr('overlay'),transient_for=app.window,modal=True,default_width=1400,default_height=850)
            self.sources=[None,None];self.counts=[0,0];self.running=False;self.pending=0;self.alive=True;self.generation=0;self.rendering=False
            root=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);self.set_child(root)
            pane=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,vexpand=True);root.append(pane)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,margin_start=12,margin_end=12,margin_top=12,margin_bottom=12)
            scroll=Gtk.ScrolledWindow(min_content_width=400,max_content_width=400,hexpand=False,hscrollbar_policy=Gtk.PolicyType.NEVER);scroll.set_size_request(400,-1);scroll.set_child(self.controls);pane.append(scroll);self.settings_panel=scroll
            self.names=[]
            for index in range(2):
                button=Gtk.Button(label=f'PDF {index+1}');self.controls.append(button)
                button.connect('clicked',lambda _,i=index:self.choose(i))
                label=Gtk.Label(wrap=True,xalign=0,max_width_chars=26);self.controls.append(label);self.names.append(label)
            self.swap=Gtk.CheckButton(label=app.tr('overlay_behind'));self.controls.append(self.swap);self.swap.connect('toggled',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('overlay_mapping'),xalign=0))
            self.mapping=Gtk.DropDown.new_from_strings([app.tr('overlay_auto'),app.tr('overlay_single'),app.tr('overlay_paired')]);self.controls.append(self.mapping);self.mapping.connect('notify::selected',self.schedule)
            self.fields={}
            for key,value,lo,hi in [('overlay_source_page',1,1,1),('overlay_opacity',100,0,100),('overlay_scale',100,1,300),('overlay_x',0,-200,200),('overlay_y',0,-200,200),('overlay_angle',0,-180,180)]:
                self.controls.append(Gtk.Label(label=app.tr(key),xalign=0));spin=Gtk.SpinButton.new_with_range(lo,hi,1);spin.set_value(value);self.fields[key]=spin;self.controls.append(spin);spin.connect('value-changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('pages'),xalign=0));self.pages=Gtk.Entry(placeholder_text='1,3-5');self.controls.append(self.pages);self.pages.connect('changed',self.schedule)
            self.controls.append(Gtk.Label(label=app.tr('watermark_preview_page'),xalign=0));self.page=Gtk.SpinButton.new_with_range(1,1,1);self.controls.append(self.page);self.page.connect('value-changed',self.schedule)
            self.save_button=Gtk.Button(label=app.tr('save_as'));self.controls.append(self.save_button);self.save_button.connect('clicked',self.save)
            right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,hexpand=True)
            right.append(Gtk.Label(label=app.tr('overlay_note'),wrap=True,xalign=0,margin_start=8,margin_end=8))
            originals=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8,homogeneous=True)
            self.pictures=[]
            for title in ('PDF 1','PDF 2',app.tr('overlay_result')):
                box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4,vexpand=True,hexpand=True);box.append(Gtk.Label(label=title))
                picture=Gtk.Picture(can_shrink=True,hexpand=True,vexpand=True);self.pictures.append(picture)
                box.append(picture)
                if len(self.pictures)<3:originals.append(box)
                else:result=box
            originals.set_size_request(-1,240);right.append(originals);right.append(result);pane.append(right)
            self.drag=Gtk.GestureDrag.new();self.drag.set_button(1);self.drag.connect('drag-begin',self.drag_begin);self.drag.connect('drag-update',self.drag_update);self.pictures[2].add_controller(self.drag);self.pictures[2].set_cursor_from_name('move')
            self.status=Gtk.Label(wrap=True,xalign=0,margin_start=12,margin_bottom=8);root.append(self.status)
            self.connect('close-request',self.closing)
            for i,path in enumerate((paths or [])[:2]):self.load(i,path)
            self.save_button.set_sensitive(False);self.present();self.schedule()
        def choose(self,index):
            app.choose_files(parent=self,tool='crop',on_selected=lambda paths:self.load(index,paths[0]),selection_title=f'PDF {index+1}')
        def load(self,index,path):
            try:
                data=Path(path).read_bytes()
                with fitz.open(stream=data,filetype='pdf') as doc:
                    if doc.needs_pass:raise ValueError('E_PASSWORD')
                    if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                    self.counts[index]=len(doc)
                self.sources[index]=data;self.names[index].set_text(Path(path).name)
                self.page.set_range(1,max(1,self.counts[0]));self.fields['overlay_source_page'].set_range(1,max(1,self.counts[1]));self.schedule()
            except Exception as exc:app.error(exc)
        def options(self):
            return dict(pages=self.pages.get_text(),overlay_behind=self.swap.get_active(),overlay_mapping=('auto','single','paired')[self.mapping.get_selected()],**{k:v.get_value_as_int() for k,v in self.fields.items()})
        def schedule(self,*_):
            self.generation+=1;self.save_button.set_sensitive(False)
            if not self.pending:self.pending=GLib.timeout_add(50,self.render)
        def texture(self,data):return Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        def render(self):
            self.pending=0
            if not self.alive or self.running or self.rendering:return False
            if not all(self.sources):return False
            self.rendering=True;generation=self.generation;opts=self.options();number=int(self.page.get_value())-1;sources=list(self.sources)
            def worker():
                pictures=[];error=None
                try:
                    second=int(opts['overlay_source_page'])-1 if opts['overlay_mapping']=='single' else 0 if self.counts[1]==1 else min(number,self.counts[1]-1)
                    for data,index in zip(sources,(number,second)):
                        with fitz.open(stream=data,filetype='pdf') as doc:
                            page=doc[index];scale=min(500/page.rect.width,450/page.rect.height);pictures.append(page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png'))
                    output=overlay_documents(*sources,opts,preview_page=number)
                    with fitz.open(stream=output,filetype='pdf') as doc:
                        page=doc[0];scale=min(850/page.rect.width,650/page.rect.height);pictures.append(page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).tobytes('png'))
                except Exception as exc:error=exc
                def finish():
                    self.rendering=False
                    if not self.alive:return False
                    if generation!=self.generation:self.schedule();return False
                    for picture,data in zip(self.pictures,pictures):picture.set_paintable(self.texture(data))
                    if error:self.pictures[2].set_paintable(None);self.status.set_text(app.tr(str(error)))
                    else:self.status.set_text('');self.save_button.set_sensitive(True)
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start();return False
        def drag_begin(self,gesture,x,y):
            self.drag_values=(self.fields['overlay_x'].get_value(),self.fields['overlay_y'].get_value())
        def drag_update(self,gesture,dx,dy):
            if self.running:return
            picture=self.pictures[2];paint=picture.get_paintable()
            if not paint:return
            scale=min(picture.get_width()/paint.get_intrinsic_width(),picture.get_height()/paint.get_intrinsic_height())
            w=paint.get_intrinsic_width()*scale;h=paint.get_intrinsic_height()*scale
            if w<=0 or h<=0:return
            x,y=self.drag_values;self.fields['overlay_x'].set_value(x+dx/w*100);self.fields['overlay_y'].set_value(y+dy/h*100)
        def save(self,*_):
            self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('overlay',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=self.options();sources=list(self.sources);self.running=True;self.controls.set_sensitive(False);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    data=overlay_documents(*sources,opts)
                    with tempfile.TemporaryDirectory(prefix='.mintpdf-',dir=destination.parent) as folder:
                        result=Path(folder)/'result.pdf';result.write_bytes(data);os.link(result,destination)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False
            if self.pending:GLib.source_remove(self.pending)
            return False
    return Overlay()

def open_creator(app):
    import gi,pymupdf as fitz,copy
    gi.require_version('Gtk','4.0');gi.require_foreign('cairo')
    from gi.repository import Gtk,Gdk,GLib
    from core import create_document
    class Creator(Gtk.Window):
        def __init__(self):
            super().__init__(title=app.tr('create'),transient_for=app.window,modal=True,default_width=1200,default_height=850)
            self.pages=[dict(width=595,height=842,items=[])];self.index=0;self.selected=None;self.updating=False;self.pending=0;self.alive=True;self.running=False;self.valid=False
            root=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=12);self.set_child(root)
            self.controls=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,margin_start=12,margin_end=12,margin_top=12,margin_bottom=12)
            scroll=Gtk.ScrolledWindow(min_content_width=320,max_content_width=320,hscrollbar_policy=Gtk.PolicyType.NEVER);scroll.set_size_request(320,-1);scroll.set_child(self.controls);root.append(scroll)
            def label(key):self.controls.append(Gtk.Label(label=app.tr(key),xalign=0,wrap=True))
            def button(key,fn):
                b=Gtk.Button(label=app.tr(key));b.connect('clicked',lambda *_:fn());self.controls.append(b);return b
            label('creator_note');label('watermark_preview_page')
            self.page=Gtk.SpinButton.new_with_range(1,1,1);self.controls.append(self.page);self.page.connect('value-changed',self.change_page)
            button('creator_add_page',self.add_page);button('creator_delete_page',self.delete_page)
            button('move_up',lambda:self.move_page(-1));button('move_down',lambda:self.move_page(1))
            label('creator_format');self.format=Gtk.DropDown.new_from_strings(['A4','A5',app.tr('creator_custom')]);self.controls.append(self.format);self.format.connect('notify::selected',self.set_format)
            self.landscape=Gtk.CheckButton(label=app.tr('creator_landscape'));self.controls.append(self.landscape);self.landscape.connect('toggled',self.set_format)
            self.spins={}
            for key,value,lo,hi in [('creator_width',210,25.4,1016),('creator_height',297,25.4,1016),('creator_margin',15,0,100),('creator_x',15,0,1016),('creator_y',15,0,1016),('creator_item_width',100,1,1016),('creator_item_height',40,1,1016),('creator_font_size',14,6,100)]:
                label(key);spin=Gtk.SpinButton.new_with_range(lo,hi,1);spin.set_digits(1);spin.set_value(value);self.spins[key]=spin;self.controls.append(spin);spin.connect('value-changed',self.changed)
            button('creator_background',self.background);button('creator_clear_background',self.clear_background)
            button('creator_add_text',self.add_text);button('creator_add_image',self.choose_image);button('creator_delete_item',self.delete_item)
            label('text');self.text=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR);textscroll=Gtk.ScrolledWindow(min_content_height=100);textscroll.set_child(self.text);self.controls.append(textscroll);self.text.get_buffer().connect('changed',self.changed)
            label('creator_font');self.font=Gtk.DropDown.new_from_strings(['Sans','Serif','Mono']);self.controls.append(self.font);self.font.connect('notify::selected',self.changed)
            label('creator_color');self.color=Gtk.DropDown.new_from_strings([app.tr(k) for k in ('creator_black','watermark_red','watermark_blue')]);self.controls.append(self.color);self.color.connect('notify::selected',self.changed)
            label('creator_align');self.align=Gtk.DropDown.new_from_strings([app.tr(k) for k in ('creator_left','creator_center','creator_right')]);self.controls.append(self.align);self.align.connect('notify::selected',self.changed)
            self.numbers=Gtk.CheckButton(label=app.tr('numbers'));self.controls.append(self.numbers);self.numbers.connect('toggled',self.schedule)
            label('watermark');self.watermark=Gtk.Entry();self.controls.append(self.watermark);self.watermark.connect('changed',self.schedule)
            self.save_button=button('save_as',self.save)
            right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,hexpand=True,vexpand=True);root.append(right)
            self.picture=Gtk.Picture(can_shrink=True,hexpand=True,vexpand=True);overlay=Gtk.Overlay();overlay.set_child(self.picture)
            self.frame=Gtk.DrawingArea(hexpand=True,vexpand=True,can_target=False);self.frame.set_draw_func(self.draw_frame);overlay.add_overlay(self.frame);right.append(overlay)
            self.status=Gtk.Label(wrap=True,xalign=0);right.append(self.status)
            gesture=Gtk.GestureDrag.new();gesture.set_button(1);gesture.connect('drag-begin',self.drag_begin);gesture.connect('drag-update',self.drag_update);gesture.connect('drag-end',lambda *_:self.schedule());self.picture.add_controller(gesture)
            self.connect('close-request',self.closing);self.render();self.present()
        def current(self):return self.pages[self.index]
        def item(self):return self.current()['items'][self.selected] if self.selected is not None else None
        def options(self):return dict(numbers=self.numbers.get_active(),watermark=self.watermark.get_text().strip())
        def refresh(self):
            self.updating=True;self.page.set_range(1,len(self.pages));self.page.set_value(self.index+1)
            for key,field in [('creator_width','width'),('creator_height','height')]:self.spins[key].set_value(self.current()[field]/(72/25.4))
            self.updating=False;self.selected=None;self.schedule()
        def change_page(self,*_):
            if self.updating:return
            self.index=int(self.page.get_value())-1;self.refresh()
        def add_page(self):
            self.pages.insert(self.index+1,dict(width=self.current()['width'],height=self.current()['height'],items=[]));self.index+=1;self.refresh()
        def delete_page(self):
            if len(self.pages)>1:self.pages.pop(self.index);self.index=min(self.index,len(self.pages)-1);self.refresh()
        def move_page(self,delta):
            target=self.index+delta
            if 0<=target<len(self.pages):self.pages[self.index],self.pages[target]=self.pages[target],self.pages[self.index];self.index=target;self.refresh()
        def set_format(self,*_):
            if self.updating:return
            mode=self.format.get_selected()
            if mode==2:return
            w,h=(210,297) if mode==0 else (148,210)
            if self.landscape.get_active():w,h=h,w
            self.updating=True;self.spins['creator_width'].set_value(w);self.spins['creator_height'].set_value(h);self.updating=False;self.changed()
        def background(self):
            def loaded(paths):
                try:
                    data=Path(paths[0]).read_bytes()
                    with fitz.open(stream=data,filetype='pdf') as doc:
                        if doc.needs_pass:raise ValueError('E_PASSWORD')
                        if not len(doc):raise ValueError('E_INPUT')
                        page=self.current();page['background']=data;page['background_page']=0
                    self.schedule()
                except Exception as exc:app.error(exc)
            app.choose_files(parent=self,tool='crop',on_selected=loaded)
        def clear_background(self):self.current().pop('background',None);self.schedule()
        def new_item(self,kind,data=None):
            page=self.current();margin=min(self.spins['creator_margin'].get_value()*72/25.4,min(page['width'],page['height'])/4)
            item=dict(kind=kind,x=margin,y=margin,w=min(280,page['width']-2*margin),h=min(120,page['height']-2*margin),text=app.tr('creator_new_text'),size=14,font='helv',color='black',align=0)
            if data:
                pix=fitz.Pixmap(data);item['data']=data;item['h']=min(item['h'],item['w']*pix.height/pix.width);item['w']=item['h']*pix.width/pix.height
            page['items'].append(item);self.selected=len(page['items'])-1;self.select_fields();self.schedule()
        def add_text(self):self.new_item('text')
        def choose_image(self):
            def loaded(paths):
                try:self.new_item('image',Path(paths[0]).read_bytes())
                except Exception as exc:app.error(exc)
            app.choose_files(parent=self,tool='images_pdf',on_selected=loaded)
        def delete_item(self):
            if self.selected is not None:self.current()['items'].pop(self.selected);self.selected=None;self.schedule()
        def select_fields(self):
            item=self.item()
            if item is None:return
            self.updating=True
            for key,field in [('creator_x','x'),('creator_y','y'),('creator_item_width','w'),('creator_item_height','h')]:self.spins[key].set_value(item[field]/(72/25.4))
            self.spins['creator_font_size'].set_value(item.get('size',14));self.text.get_buffer().set_text(item.get('text',''))
            self.font.set_selected(('helv','tiro','cour').index(item.get('font','helv')));self.color.set_selected(('black','red','blue').index(item.get('color','black')));self.align.set_selected(item.get('align',0));self.updating=False
        def changed(self,*_):
            if self.updating:return
            page=self.current();page['width']=self.spins['creator_width'].get_value()*72/25.4;page['height']=self.spins['creator_height'].get_value()*72/25.4
            item=self.item()
            if item is not None:
                for key,field in [('creator_x','x'),('creator_y','y'),('creator_item_width','w'),('creator_item_height','h')]:item[field]=self.spins[key].get_value()*72/25.4
                buf=self.text.get_buffer();item.update(text=buf.get_text(buf.get_start_iter(),buf.get_end_iter(),True),size=self.spins['creator_font_size'].get_value(),font=('helv','tiro','cour')[self.font.get_selected()],color=('black','red','blue')[self.color.get_selected()],align=self.align.get_selected())
            self.schedule()
        def bounds(self):
            paint=self.picture.get_paintable()
            if not paint:return None
            scale=min(self.picture.get_width()/paint.get_intrinsic_width(),self.picture.get_height()/paint.get_intrinsic_height())
            w=paint.get_intrinsic_width()*scale;h=paint.get_intrinsic_height()*scale
            if min(w,h)<=0:return None
            return (self.picture.get_width()-w)/2,(self.picture.get_height()-h)/2,w/self.current()['width'],h/self.current()['height']
        def draw_frame(self,area,ctx,width,height):
            item=self.item();bounds=self.bounds()
            if item is None or not bounds:return
            x,y,sx,sy=bounds;x+=item['x']*sx;y+=item['y']*sy;w=item['w']*sx;h=item['h']*sy
            ctx.set_source_rgb(.12,.55,.9);ctx.set_line_width(2);ctx.rectangle(x,y,w,h);ctx.stroke()
            for px,py in ((x,y),(x+w,y),(x,y+h),(x+w,y+h)):
                ctx.rectangle(px-5,py-5,10,10);ctx.fill()
        def drag_begin(self,gesture,x,y):
            self.drag=None
            if self.running:return
            bounds=self.bounds()
            if not bounds:return
            left,top,sx,sy=bounds;px=(x-left)/sx;py=(y-top)/sy
            item=self.item()
            if item:
                for hx,hy,signx,signy in ((item['x'],item['y'],-1,-1),(item['x']+item['w'],item['y'],1,-1),(item['x'],item['y']+item['h'],-1,1),(item['x']+item['w'],item['y']+item['h'],1,1)):
                    if abs(px-hx)*sx<=10 and abs(py-hy)*sy<=10:self.drag=('resize',copy.deepcopy(item),sx,sy,signx,signy);return
            self.selected=None
            for index in reversed(range(len(self.current()['items']))):
                item=self.current()['items'][index]
                if item['x']<=px<=item['x']+item['w'] and item['y']<=py<=item['y']+item['h']:self.selected=index;self.drag=('move',copy.deepcopy(item),sx,sy,1,1);self.select_fields();break
            self.frame.queue_draw()
        def drag_update(self,gesture,dx,dy):
            if not self.drag:return
            mode,old,sx,sy,signx,signy=self.drag;item=self.item();page=self.current()
            if mode=='move':item['x']=max(0,min(page['width']-item['w'],old['x']+dx/sx));item['y']=max(0,min(page['height']-item['h'],old['y']+dy/sy))
            else:
                factor=max(.05,1+(dx/sx*signx*old['w']+dy/sy*signy*old['h'])/(old['w']**2+old['h']**2));w=old['w']*factor;h=old['h']*factor
                x=old['x'] if signx>0 else old['x']+old['w']-w;y=old['y'] if signy>0 else old['y']+old['h']-h
                if x>=0 and y>=0 and x+w<=page['width'] and y+h<=page['height']:item.update(x=x,y=y,w=w,h=h)
            self.select_fields();self.schedule()
        def schedule(self,*_):
            if not self.pending:self.pending=GLib.timeout_add(40,self.render)
        def render(self):
            self.pending=0
            if not self.alive:return False
            try:
                data=create_document(self.pages,self.options(),self.index)
                with fitz.open(stream=data,filetype='pdf') as doc:
                    page=doc[0];scale=min(850/page.rect.width,850/page.rect.height);pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                self.picture.set_paintable(Gdk.Texture.new_from_bytes(GLib.Bytes.new(pix.tobytes('png'))));self.valid=True;self.status.set_text('')
            except Exception as exc:self.valid=False;self.status.set_text(app.tr(str(exc)))
            self.frame.queue_draw();self.save_button.set_sensitive(self.valid and not self.running);return False
        def save(self):
            if self.valid:self.picker=select_save_target(self,app.tr('save_as'),output_suggestion('create',app.config.get('output_dir')),self.write,app.error,app.tr('save'))
        def write(self,target):
            spec=copy.deepcopy(self.pages);opts=self.options();self.running=True;self.controls.set_sensitive(False)
            def worker():
                error=None
                try:
                    destination=Path(target)
                    if destination.suffix.lower()!='.pdf':raise ValueError('E_INPUT')
                    data=create_document(spec,opts)
                    with tempfile.TemporaryDirectory(prefix='.mintpdf-',dir=destination.parent) as folder:
                        result=Path(folder)/'result.pdf';result.write_bytes(data);os.link(result,destination)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.controls.set_sensitive(True)
                    if error:app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
        def closing(self,*_):
            if self.running:return True
            self.alive=False
            if self.pending:GLib.source_remove(self.pending)
            return False
    return Creator()

def open_converter(app,path):
    import gi
    gi.require_version('Gtk','4.0')
    from gi.repository import Gtk,GLib
    from core import conversion_suffix
    class Converter(Gtk.Window):
        def __init__(self):
            super().__init__(title=app.tr('convert'),transient_for=app.window,modal=True,default_width=540)
            self.running=False;self.cancel=threading.Event();self.formats=('txt','html','odt','png','jpg')
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin_start=20,margin_end=20,margin_top=20,margin_bottom=20);self.set_child(box)
            box.append(Gtk.Label(label=Path(path).name,wrap=True,xalign=0));box.append(Gtk.Label(label=app.tr('convert_note'),wrap=True,xalign=0,max_width_chars=60))
            self.format=Gtk.DropDown.new_from_strings(['TXT','HTML','ODT','PNG (ZIP)','JPG (ZIP)']);box.append(self.format)
            self.dpi=Gtk.DropDown.new_from_strings(['72 DPI','150 DPI','300 DPI']);self.dpi.set_selected(1);box.append(self.dpi)
            self.format.connect('notify::selected',lambda *_:self.dpi.set_sensitive(self.format.get_selected()>=3));self.dpi.set_sensitive(False)
            self.save_button=Gtk.Button(label=app.tr('save_as'));box.append(self.save_button);self.save_button.connect('clicked',self.save)
            self.cancel_button=Gtk.Button(label=app.tr('cancel'),visible=False);box.append(self.cancel_button);self.cancel_button.connect('clicked',lambda *_:self.cancel.set())
            self.status=Gtk.Label(wrap=True,xalign=0);box.append(self.status);self.connect('close-request',lambda *_:self.running);self.present()
        def save(self,*_):
            suffix=conversion_suffix(self.formats[self.format.get_selected()]);suggested=Path(output_suggestion('convert',app.config.get('output_dir'))).with_suffix(suffix)
            while suggested.exists():suggested=suggested.with_name(suggested.stem+'-2'+suffix)
            self.picker=select_save_target(self,app.tr('save_as'),suggested,self.write,app.error,app.tr('save'))
        def write(self,target):
            opts=dict(convert_format=self.formats[self.format.get_selected()],image_dpi=(72,150,300)[self.dpi.get_selected()],cancel_event=self.cancel)
            self.cancel.clear();self.running=True;self.format.set_sensitive(False);self.dpi.set_sensitive(False);self.save_button.set_sensitive(False);self.cancel_button.set_visible(True);self.status.set_text(app.tr('working'))
            def worker():
                error=None
                try:process('convert',[path],target,opts)
                except Exception as exc:error=exc
                def finish():
                    self.running=False;self.format.set_sensitive(True);self.dpi.set_sensitive(self.format.get_selected()>=3);self.save_button.set_sensitive(True);self.cancel_button.set_visible(False)
                    if error:self.status.set_text('');app.error(error)
                    else:self.status.set_text(app.tr('saved')+'\n'+str(target))
                    return False
                GLib.idle_add(finish)
            threading.Thread(target=worker,daemon=True).start()
    return Converter()

if __name__=='__main__':
    raise SystemExit(main())
