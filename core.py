"""mintPDF: Werkzeugkatalog und PDF-Verarbeitung, GPL-3.0-only.

Alle Ausgaben werden zuerst temporär erzeugt. Bestehende Dateien werden niemals
überschrieben. PyMuPDF ist optional; externe Werkzeuge werden über PATH erkannt.
Neue Werkzeuge im Katalog TOOLS und in process() ergänzen.
"""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import tempfile
import zipfile
import re

VERSION = '1.39.3'
"""Zentrale Funktionsdefinitionen für Verarbeitung und Navigation."""
from dataclasses import dataclass

# Kennung, deutsches/englisches Label, Abhängigkeit, Eingabeart, Parameterart
TOOLS = [
 ('merge','PDF zusammenfügen','Merge PDFs','pymupdf','many',''),
 ('crop','PDF-Seiten zuschneiden','Crop PDF pages','pymupdf','one',''),
 ('split','PDF trennen','Split PDF','pymupdf','one',''),
 ('document_info','Dokumenteninformationen','Document information','pymupdf','one','check'),
 ('pdfa_check','PDF/A prüfen','Validate PDF/A','verapdf','one','check'),
 ('pdfa','PDF/A erzeugen','Create PDF/A','gs','one',''),
 ('compress','PDF komprimieren','Compress PDF','gs','one',''),
 ('edit','PDF bearbeiten','Edit PDF','libreoffice','one','external'),
 ('form','Formular aus Muster erstellen','Create form from template','pymupdf','one',''),
 ('signature_image','Unterschrift einfügen','Insert signature','pymupdf','one',''),
 ('convert','PDF konvertieren','Convert PDF','pymupdf','one',''),
 ('image_crop','Bild in PDF zuschneiden','Crop PDF image','pymupdf','one',''),
 ('image_rotate','Bild in PDF drehen','Rotate PDF image','pymupdf','one',''),
 ('image_resize','Bildgröße und Position ändern','Resize and move PDF images','pymupdf','one',''),
 ('images_pdf','Bild / Unterschrift einfügen','Insert image / signature','pymupdf','many',''),
 ('pdf_images','PDF in Bilder','PDF to images','pymupdf','one',''),
 ('extract_images','Bilder extrahieren','Extract images','pymupdf','one',''),
 ('encrypt','PDF verschlüsseln','Encrypt PDF','pymupdf','one','password'),
 ('decrypt','Passwortschutz entfernen','Remove password','pymupdf','one','password'),
 ('rotate','PDF Seiten drehen','Rotate PDF pages','pymupdf','one','pages_angle'),
 ('delete','PDF Seiten löschen','Delete PDF pages','pymupdf','one','pages'),
 ('extract','PDF Seiten extrahieren','Extract PDF pages','pymupdf','one','pages'),
 ('sort','PDF Seiten sortieren','Reorder PDF pages','pymupdf','one','pages'),
 ('web','Webseite in PDF','Webpage to PDF','wkhtmltopdf','one',''),
 ('text_extract','Text extrahieren','Extract text','pymupdf','one',''),
 ('text_search','Text suchen','Search text','pymupdf','one',''),
 ('ocr','Text per OCR erkennen','Recognize text with OCR','ocrmypdf','one',''),
 ('watermark','Wasserzeichen einfügen','Add watermark','pymupdf','one','text'),
 ('annotations','Anmerkungen hinzufügen','Add annotations','pymupdf','one',''),
 ('numbers','Seitenzahlen einfügen','Add page numbers','pymupdf','one',''),
 ('overlay','PDFs übereinanderlegen','Overlay PDFs','pymupdf','two',''),
 ('compare','PDFs vergleichen','Compare PDFs','pymupdf','two',''),
 ('optimize','PDF optimieren','Optimize PDF','pymupdf','one',''),
 ('redact','PDF schwärzen','Redact PDF','pymupdf','one','text'),
 ('create','PDF erstellen','Create PDF','pymupdf','none','text'),
]
BY_ID = {t[0]: t for t in TOOLS}
ZIP_TOOLS = {'split','pdf_images','extract_images'}


GROUPS = ('pages', 'images', 'text', 'content', 'create', 'optimize', 'security', 'inspect')
GROUP_MEMBERS = {
    'pages': ('merge', 'split', 'sort', 'rotate', 'delete', 'extract', 'crop'),
    'images': ('images_pdf', 'extract_images', 'image_resize', 'image_rotate', 'image_crop'),
    'text': ('ocr', 'text_search'),
    'content': ('watermark', 'numbers', 'annotations', 'overlay'),
    'create': ('create', 'convert', 'web', 'edit', 'form'),
    'optimize': ('compress', 'optimize', 'pdfa'),
    'security': ('encrypt', 'decrypt', 'redact'),
    'inspect': ('compare', 'document_info', 'pdfa_check'),
}

@dataclass(frozen=True)
class Function:
    id: str
    group: str
    icon: str
    handler: str | None
    def status(self, gui=True):
        if self.handler is None:
            return False, 'not_implemented', ''
        try:
            if not available(self.id,gui=gui):
                return False, 'tool_missing', ', '.join(missing_tools(self.id,gui=gui))
            if BY_ID[self.id][3] == 'pymupdf':
                import pymupdf
                from packaging.version import Version
                if Version(pymupdf.VersionBind) < Version('1.24.0'):
                    return False, 'unsupported_version', 'PyMuPDF >= 1.24.0'
            return True, '', ''
        except Exception as exc:
            return False, 'prerequisite_failed', type(exc).__name__
    def matches(self, query, translate):
        text = ' '.join((translate(self.id), translate('description_' + self.id),
                         translate('keywords_' + self.id), self.id))
        return query.casefold().strip() in text.casefold()

FUNCTIONS = tuple(Function(key, group, key if key in BY_ID else 'group_' + group,
                           'tool_dialog' if key in BY_ID else None)
                  for group in GROUPS for key in GROUP_MEMBERS[group])
FUNCTION_BY_ID = {f.id: f for f in FUNCTIONS}

def can_dispatch(key, busy=False):
    if busy:
        return False, 'processing', ''
    function = FUNCTION_BY_ID.get(key)
    if function is None:
        return False, 'not_implemented', ''
    return function.status()



def validator_command():
    bundled=Path(__file__).resolve().parent/'verapdf/verapdf'
    if bundled.is_file() and os.access(bundled,os.X_OK):return str(bundled)
    command=shutil.which('verapdf')
    if command:return command
    local=Path.home()/'.local/bin/verapdf'
    return str(local) if local.is_file() and os.access(local,os.X_OK) else None


def available(tool,gui=False):
    """Tatsächliche Importfähigkeit bzw. ausführbare Datei prüfen."""
    dep = BY_ID[tool][3]
    if tool in ('pdfa','pdfa_check'):return not missing_tools(tool,gui=gui)
    if dep == 'pymupdf':
        try:
            import pymupdf
            if gui and tool in ('redact','compare','crop','images_pdf','signature_image','create'):
                import cairo,gi
                gi.require_foreign('cairo')
            return True
        except (ImportError, OSError, ValueError):
            return False
    if tool=='ocr': return all(shutil.which(name) for name in ('ocrmypdf','tesseract'))
    return shutil.which(dep) is not None


def missing_tools(tool,gui=False):
    """Fehlende Laufzeitwerkzeuge für ausgegraute Kacheln benennen."""
    dependency=BY_ID[tool][3]
    if dependency=='pymupdf':
        missing=[] if available('merge') else ['PyMuPDF']
        if gui and tool in ('redact','compare','crop','images_pdf','signature_image','create'):
            try:
                import cairo,gi
                gi.require_foreign('cairo')
            except (ImportError,OSError,ValueError):missing.append('cairo / gi-cairo')
        return missing
    dependencies=('gs','verapdf') if tool=='pdfa' else ('ocrmypdf','tesseract') if tool=='ocr' else (dependency,)
    missing=[name for name in dependencies if not (validator_command() if name=='verapdf' else shutil.which(name))]
    if tool=='pdfa' and not available('merge'):missing.append('PyMuPDF')
    return missing


INSTALL_HINTS={
    'cairo / gi-cairo':'sudo apt install python3-cairo python3-gi-cairo',
    'PyMuPDF':'sudo apt install python3-venv python3-pip; danach im mintPDF-Ordner: sh setup_dependencies.sh',
    'gs':'sudo apt install ghostscript',
    'verapdf':'veraPDF CLI und Java einrichten: https://docs.verapdf.org/install/',
    'libreoffice':'sudo apt install libreoffice',
    'wkhtmltopdf':'sudo apt install wkhtmltopdf (sofern in den Paketquellen verfügbar)',
    'ocrmypdf':'sudo apt install ocrmypdf',
    'tesseract':'sudo apt install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng',
}

def dependency_report():
    """Installationsvorschläge nur ausgeben; niemals automatisch installieren."""
    missing={}
    for tool in TOOLS:
        if tool[0] not in FUNCTION_BY_ID:continue
        for name in missing_tools(tool[0]):missing.setdefault(name,[]).append(tool[0])
    return [(name,', '.join(ids),INSTALL_HINTS.get(name,'')) for name,ids in sorted(missing.items())]


def ocr_languages():
    """Nur tatsächlich installierte Tesseract-Sprachen anbieten."""
    if not shutil.which('tesseract'): return []
    try:
        text=subprocess.check_output(['tesseract','--list-langs'],stderr=subprocess.STDOUT,timeout=10).decode(errors='replace')
        return sorted(line.strip() for line in text.splitlines() if re.fullmatch(r'[\w/]+',line.strip()) and line.strip()!='osd')
    except (OSError,subprocess.SubprocessError): return []


def processing_command(tool, source, destination, options):
    """Geprüfte Ghostscript-/OCRmyPDF-Argumente ohne Shell erzeugen.

    Ghostscript wird für reine Kompression verwendet; OCRmyPDF für OCR.
    Konservative Vorgaben: ebook, bzw. Textseiten überspringen und normales PDF.
    Ältere OCRmyPDF-Versionen verstehen die hier verwendeten Legacy-Modusschalter.
    """
    if tool=='compress':
        profile=options.get('gs_profile','ebook')
        if profile not in ('screen','ebook','printer','prepress','default'): raise ValueError('E_OPTIONS')
        return ['gs','-dSAFER','-dBATCH','-dNOPAUSE','-sDEVICE=pdfwrite',f'-dPDFSETTINGS=/{profile}',f'-sOutputFile={destination}',str(source)]
    if tool!='ocr': raise ValueError('E_OPTIONS')
    mode=options.get('ocr_mode','skip')
    output_type=options.get('ocr_output','pdf')
    optimization=str(options.get('ocr_optimize','1'))
    language=options.get('ocr_language','eng')
    if mode not in ('skip','redo') or output_type not in ('pdf','pdfa') or optimization not in ('0','1','2','3'):
        raise ValueError('E_OPTIONS')
    if not isinstance(language,str) or not re.fullmatch(r'[\w/]+(?:\+[\w/]+)*',language): raise ValueError('E_OPTIONS')
    if mode=='redo' and options.get('ocr_deskew'): raise ValueError('E_OPTIONS')
    command=['ocrmypdf','--skip-text' if mode=='skip' else '--redo-ocr','--output-type',output_type,'--optimize',optimization,'--language',language]
    if options.get('ocr_rotate'):command.append('--rotate-pages')
    if options.get('ocr_deskew'):command.append('--deskew')
    command.extend([str(source),str(destination)])
    return command


def pages(spec, count):
    """1-basierte Liste mit Bereichen in gewünschter Reihenfolge auswerten."""
    if not spec.strip():
        return list(range(count))
    result = []
    for part in spec.split(','):
        bits = part.strip().split('-')
        if len(bits) == 1:
            result.append(int(bits[0])-1)
        elif len(bits) == 2:
            a,b = map(int,bits)
            result.extend(range(a-1,b,1) if b >= a else range(a-1,b-2,-1))
        else:
            raise ValueError('E_INPUT')
    if not result or any(p < 0 or p >= count for p in result):
        raise ValueError('E_INPUT')
    return result


import threading,time,signal
_job=threading.local()

def check_cancel():
    event=getattr(_job,'cancel',None)
    if event is not None and event.is_set():raise RuntimeError('E_CANCELLED')

def run_command(args, capture=False, accepted_codes=(0,)):
    """Cancel and reap the complete external process group."""
    check_cancel()
    with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
        child=subprocess.Popen(args,stdout=stdout,stderr=stderr,start_new_session=True)
        deadline=time.monotonic()+900
        try:
            while child.poll() is None:
                check_cancel()
                if time.monotonic()>deadline:raise RuntimeError('E_TOOL')
                time.sleep(.05)
            check_cancel()
            if child.returncode not in accepted_codes:
                import logging
                stderr.seek(0);stdout.seek(0)
                detail=(stderr.read()+stdout.read()).decode('utf-8',errors='replace')[-4000:]
                logging.error('Werkzeug %s, Exit %s: %s',Path(args[0]).name,child.returncode,detail)
                raise RuntimeError('E_TOOL')
            if capture:
                stdout.seek(0)
                return stdout.read()
        except BaseException:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # Descendants may survive after the group leader exits.
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
            raise


def split_groups(count, options):
    """0-basierte Seitengruppen für die vier Trennarten validieren.

    Bereiche sind durch Semikolon getrennt; jede Gruppe wird eine PDF.
    Trennstellen sind 1-basierte Seiten, nach denen ein neuer Teil beginnt.
    """
    try:
        mode=options.get('split_mode','single')
        if count<1: raise ValueError()
        if mode=='single': return [[i] for i in range(count)]
        if mode=='chunks':
            size=int(options.get('split_size',''))
            if size<1: raise ValueError()
            return [list(range(i,min(i+size,count))) for i in range(0,count,size)]
        if mode=='cuts':
            cuts=[int(s.strip()) for s in options.get('split_cuts','').split(',')]
            if not cuts or cuts!=sorted(set(cuts)) or any(i<1 or i>=count for i in cuts): raise ValueError()
            bounds=[0,*cuts,count]
            return [list(range(a,b)) for a,b in zip(bounds,bounds[1:])]
        if mode=='ranges':
            specs=options.get('split_ranges','').split(';')
            if any(not part.strip() for part in specs): raise ValueError()
            return [pages(spec,count) for spec in specs]
        raise ValueError()
    except (ValueError,TypeError,AttributeError) as exc:
        raise ValueError('E_SPLIT') from exc


def pdf_page_count(path):
    """PDF vor Anzeige der Trennmöglichkeiten prüfen; Datei sofort schließen."""
    import pymupdf
    with pymupdf.open(path) as document:
        if document.needs_pass: raise ValueError('E_PASSWORD')
        if not document.is_pdf or document.page_count<1: raise ValueError('E_INPUT')
        return document.page_count


def pdf_display_date(value):
    """PDF metadata dates, including offsets, displayed in Berlin local time."""
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo
    match=re.fullmatch(r"(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(Z|[+-]\d{2}'?\d{2}'?)?",value or '')
    if not match:return ''
    parts=match.groups()
    try:
        date=datetime(*[int(v) if v else (1 if i in (1,2) else 0) for i,v in enumerate(parts[:6])])
        offset=parts[6]
        if offset:
            tz=timezone.utc if offset=='Z' else timezone((1 if offset[0]=='+' else -1)*timedelta(hours=int(offset[1:3]),minutes=int(offset[3:].replace("'",''))))
            date=date.replace(tzinfo=tz).astimezone(ZoneInfo('Europe/Berlin'))
        return date.strftime('%d.%m.%Y %H:%M:%S')
    except ValueError:return ''

def document_information(source):
    """Read document properties without extracting contents or changing the file."""
    import pymupdf as fitz
    from collections import Counter
    path=Path(source).resolve(strict=True)
    try:document=fitz.open(path)
    except fitz.FileDataError as exc:raise ValueError('E_INPUT') from exc
    with document as doc:
        if not doc.is_pdf:raise ValueError('E_INPUT')
        if doc.needs_pass and not doc.authenticate(''):raise ValueError('E_PASSWORD')
        meta=doc.metadata or {}
        result={'path':str(path),'size':path.stat().st_size,'pages':len(doc),
                'format':meta.get('format',''),'encrypted':doc.xref_get_key(-1,'Encrypt')[0]!='null',
                **{key:meta.get(key,'') or '' for key in ('title','author','subject','keywords','creator','producer')},
                'created':pdf_display_date(meta.get('creationDate')),
                'modified':pdf_display_date(meta.get('modDate')),
                'attachments':doc.embfile_count(),'bookmarks':len(doc.get_toc()),
                'links':0,'forms':0,'annotations':0,'images':0}
        sizes=Counter()
        for page in doc:
            check_cancel()
            sizes[(round(page.rect.width*25.4/72,1),round(page.rect.height*25.4/72,1),page.rotation)]+=1
            result['links']+=len(page.get_links())
            result['forms']+=sum(1 for _ in page.widgets() or [])
            result['annotations']+=sum(1 for _ in page.annots() or [])
            result['images']+=len(page.get_images())
        result['page_sizes']=[{'width':w,'height':h,'rotation':r,'count':count} for (w,h,r),count in sizes.items()]
        return result


def pdf_security(path):
    """Verschlüsselung und Öffnungssperre getrennt prüfen, keine Geheimnisse loggen."""
    import pymupdf as fitz
    with fitz.open(path) as doc:
        if not doc.is_pdf:raise ValueError('E_INPUT')
        encrypted=doc.xref_get_key(-1,'Encrypt')[0]!='null'
        locked=bool(doc.needs_pass and not doc.authenticate(''))
        return {'encrypted':encrypted,'locked':locked}


def decrypt_pdf(source,result,password=''):
    """Gesamtes Dokument einschließlich Formularen und Lesezeichen erhalten."""
    import pymupdf as fitz
    with fitz.open(source) as doc:
        if not doc.is_pdf:raise ValueError('E_INPUT')
        if (doc.needs_pass or password) and doc.xref_get_key(-1,'Encrypt')[0]!='null' and not doc.authenticate(password):raise ValueError('E_PASSWORD')
        doc.save(result,encryption=fitz.PDF_ENCRYPT_NONE,garbage=4,deflate=True)


def apply_watermark(page,text,options):
    """Identical geometry for preview and saved PDF."""
    import pymupdf as fitz
    import math
    try:
        angle=float(options.get('watermark_angle',45))
        opacity=float(options.get('watermark_opacity',20))/100
        size=float(options.get('watermark_size',72))
        shade=options.get('watermark_color','gray')
        color={'gray':(.4,.4,.4),'red':(.8,.1,.1),'blue':(.1,.25,.75)}[shade]
        if not (-90<=angle<=90 and 0<opacity<=1 and 8<=size<=200):raise ValueError()
    except (ValueError,TypeError,KeyError):raise ValueError('E_OPTIONS')
    # Fit the rotated text inside the visible page with a safe margin.
    width=fitz.get_text_length(text,fontsize=size)
    rad=math.radians(angle);c=abs(math.cos(rad));sn=abs(math.sin(rad))
    scale=min(1,(page.rect.width-48)/max(1,width*c+size*sn),(page.rect.height-48)/max(1,width*sn+size*c))
    size*=scale;width*=scale
    center=fitz.Point(page.rect.width/2,page.rect.height/2)
    point=fitz.Point(center.x-width/2,center.y+size*.3)
    page.insert_text(point,text,fontsize=size,color=color,fill_opacity=opacity,morph=(center,fitz.Matrix(angle)),overlay=True)


def apply_page_number(page,index,options):
    import pymupdf as fitz
    try:
        size=float(options.get('number_size',12));x=float(options.get('number_x',50))/100;y=float(options.get('number_y',95))/100;start=int(options.get('number_start',1))
        if not (8<=size<=100 and 0<=x<=1 and 0<=y<=1 and start>=0):raise ValueError()
    except (TypeError,ValueError):raise ValueError('E_OPTIONS')
    text=options.get('text','Seite ##').strip().replace('##',str(start+index))
    if not text:raise ValueError('E_INPUT')
    width=fitz.get_text_length(text,fontsize=size);size*=min(1,(page.rect.width-24)/max(width,1));width=fitz.get_text_length(text,fontsize=size)
    px=max(12,min(page.rect.width-width-12,page.rect.width*x-width/2));py=max(size+4,min(page.rect.height-12,page.rect.height*y))
    page.insert_text((px,py),text,fontsize=size,color=(0,0,0),overlay=True)


def apply_annotation(page,text,options):
    import pymupdf as fitz
    try:
        x=float(options.get('note_x',10))/100;y=float(options.get('note_y',10))/100
        size=float(options.get('note_size',12))
        if not (0<=x<=1 and 0<=y<=1 and 8<=size<=48):raise ValueError()
    except (TypeError,ValueError):raise ValueError('E_OPTIONS')
    if not text.strip():raise ValueError('E_INPUT')
    point=fitz.Point(max(4,min(page.rect.width-28,page.rect.width*x)),max(4,min(page.rect.height-28,page.rect.height*y)))
    annotation=page.add_text_annot(point,text,icon='Note')
    annotation.set_colors(stroke=(1,.8,0));annotation.update()


def apply_signature(page,image,options):
    import pymupdf as fitz
    try:
        x=float(options.get('signature_x',10))/100;y=float(options.get('signature_y',75))/100
        width=float(options.get('signature_width',25))/100
        if not (0<=x<=1 and 0<=y<=1 and .01<=width<=1):raise ValueError()
        pix=fitz.Pixmap(image);height=width*page.rect.width*pix.height/pix.width
        w=width*page.rect.width
        scale=min(1,(page.rect.height-8)/height);w*=scale;height*=scale
        left=min(page.rect.width-w-4,max(4,x*page.rect.width));top=min(page.rect.height-height-4,max(4,y*page.rect.height))
        page.insert_image(fitz.Rect(left,top,left+w,top+height),stream=image,overlay=True)
    except (TypeError,ValueError,RuntimeError):raise ValueError('E_INPUT')


def overlay_documents(first,second,options=None,preview_page=None):
    """Render and export the same vector PDF composition."""
    import pymupdf as fitz
    options=options or {}
    with fitz.open(stream=first,filetype='pdf') as base,fitz.open(stream=second,filetype='pdf') as layer,fitz.open(stream=first,filetype='pdf') as out:
        if base.needs_pass or layer.needs_pass:raise ValueError('E_PASSWORD')
        if not base.is_pdf or not layer.is_pdf or not len(base) or not len(layer):raise ValueError('E_INPUT')
        try:
            opacity=float(options.get('overlay_opacity',100))/100
            scale=float(options.get('overlay_scale',100))/100
            x=float(options.get('overlay_x',0))/100;y=float(options.get('overlay_y',0))/100
            angle=float(options.get('overlay_angle',0))
            mapping=options.get('overlay_mapping','auto')
            selected_page=int(options.get('overlay_source_page',1))-1
            if not (0<=opacity<=1 and .01<=scale<=3 and -2<=x<=2 and -2<=y<=2 and -180<=angle<=180):raise ValueError()
            if mapping not in ('auto','single','paired'):raise ValueError()
            if mapping=='single' and not 0<=selected_page<len(layer):raise ValueError()
            if mapping=='paired' and len(layer)<len(base):raise ValueError()
            if mapping=='auto' and len(layer) not in (1,len(base)):raise ValueError()
        except (ValueError,TypeError):raise ValueError('E_OPTIONS')
        chosen=set(pages(options.get('pages',''),len(base)))
        indices=range(len(base)) if preview_page is None else [preview_page]
        for i in indices:
            check_cancel()
            if not 0<=i<len(base):raise ValueError('E_INPUT')
            # Modify a private copy of PDF 1, retaining its document-level objects.
            page=out[i]
            if i not in chosen or opacity==0:continue
            source=selected_page if mapping=='single' else 0 if len(layer)==1 else i
            rect=fitz.Rect(page.rect.width*x,page.rect.height*y,page.rect.width*(x+scale),page.rect.height*(y+scale))
            before=set(page.get_contents())
            page.show_pdf_page(rect,layer,source,rotate=angle,overlay=not options.get('overlay_behind',False))
            if opacity<1:
                kind,resources=out.xref_get_key(page.xref,'Resources')
                rx=int(resources.split()[0]) if kind=='xref' else page.xref
                prefix='' if kind=='xref' else 'Resources/'
                out.xref_set_key(rx,prefix+'ExtGState/MPOverlay',f'<</Type/ExtGState/ca {opacity}/CA {opacity}>>')
                for xref in set(page.get_contents())-before:
                    stream=out.xref_stream(xref)
                    out.update_stream(xref,b'q /MPOverlay gs '+stream+b' Q')
        if preview_page is not None:
            out.select([preview_page])
        return out.tobytes(garbage=4,deflate=True)


def create_document(spec,options=None,preview_page=None):
    """Shared editor preview/export renderer; dimensions in PDF points."""
    import pymupdf as fitz
    options=options or {}
    if not isinstance(spec,list) or not spec:raise ValueError('E_INPUT')
    with fitz.open() as out:
        indices=range(len(spec)) if preview_page is None else [preview_page]
        for index in indices:
            check_cancel()
            entry=spec[index];width=float(entry['width']);height=float(entry['height'])
            if not (72<=width<=2880 and 72<=height<=2880):raise ValueError('E_OPTIONS')
            page=out.new_page(width=width,height=height)
            if entry.get('background'):
                with fitz.open(stream=entry['background'],filetype='pdf') as background:
                    page.show_pdf_page(page.rect,background,entry.get('background_page',0))
            for item in entry.get('items',[]):
                rect=fitz.Rect(item['x'],item['y'],item['x']+item['w'],item['y']+item['h'])
                if rect.is_empty or not page.rect.contains(rect):raise ValueError('E_EDITOR_BOUNDS')
                if item['kind']=='image':page.insert_image(rect,stream=item['data'],keep_proportion=True)
                else:
                    color={'black':(0,0,0),'red':(.8,.1,.1),'blue':(.1,.25,.75)}[item.get('color','black')]
                    if page.insert_textbox(rect,item.get('text',''),fontsize=item.get('size',14),fontname=item.get('font','helv'),color=color,align=item.get('align',0))<0:raise ValueError('E_EDITOR_TEXT_FIT')
            if options.get('watermark'):apply_watermark(page,options['watermark'],{})
            if options.get('numbers'):apply_page_number(page,index,{'text':'Seite ##'})
        return out.tobytes(garbage=4,deflate=True)


def conversion_suffix(format):
    if format not in ('txt','html','odt','png','jpg'):raise ValueError('E_OPTIONS')
    return '.zip' if format in ('png','jpg') else '.'+format

def conversion_links(page):
    """PDF annotations are separate from extracted text; retain their targets."""
    import pymupdf as fitz
    links=[]
    for link in page.get_links():
        if link.get('kind')==fitz.LINK_URI:
            target=link.get('uri','')
            from urllib.parse import urlsplit
            if urlsplit(target).scheme.lower() not in ('http','https','mailto','ftp'):continue
        elif link.get('kind')==fitz.LINK_GOTO and link.get('page',-1)>=0:
            target='#page-'+str(link['page']+1)
        else:continue
        label=page.get_textbox(link['from']).strip() or target
        links.append((label,target))
    return links

def convert_pdf(source,result,options):
    import pymupdf as fitz
    import html
    from xml.sax.saxutils import escape
    format=options.get('convert_format','txt');conversion_suffix(format)
    with fitz.open(source) as doc:
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
        if format in ('png','jpg'):
            dpi=int(options.get('image_dpi',150))
            if dpi not in (72,150,300):raise ValueError('E_OPTIONS')
            with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
                for index,page in enumerate(doc):
                    check_cancel();archive.writestr(f'page-{index+1:04}.{format}',page.get_pixmap(dpi=dpi,alpha=False).tobytes('png' if format=='png' else 'jpeg'))
            return
        if format=='html':
            pieces=['<!doctype html><html><head><meta charset="utf-8"><title>'+html.escape(Path(source).name)+'</title><style>section > div {position:relative;overflow:hidden;margin:1em auto;background:white;} section > div p {position:absolute;margin:0;white-space:pre;} section > div img {position:absolute;} .pdf-links {position:relative;} body {background:#eee;} a {cursor:pointer;}</style></head><body>']
            for index,page in enumerate(doc):
                check_cancel()
                # Render the page reliably, including scanned text and embedded fonts.
                # Keep a selectable text layer and independent clickable annotations.
                import base64
                width,height=page.rect.width,page.rect.height
                bitmap=base64.b64encode(page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).tobytes('png')).decode('ascii')
                page_html=f'<div style="position:relative;width:{width}pt;height:{height}pt"><img alt="" src="data:image/png;base64,{bitmap}" style="left:0;top:0;width:{width}pt;height:{height}pt">'
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        for span in line['spans']:
                            x0,y0,x1,y1=span['bbox']
                            page_html+='<span style="position:absolute;z-index:2;color:transparent;white-space:pre;left:'+str(x0)+'pt;top:'+str(y0)+'pt;font-size:'+str(span['size'])+'pt">'+html.escape(span['text'])+'</span>'
                page_html+='</div>' 
                overlays=[]
                targets=iter(conversion_links(page))
                for link in page.get_links():
                    # Use the same target policy as conversion_links.
                    if link.get('kind')==fitz.LINK_URI:
                        from urllib.parse import urlsplit
                        if urlsplit(link.get('uri','')).scheme.lower() not in ('http','https','mailto','ftp'):continue
                    elif not (link.get('kind')==fitz.LINK_GOTO and link.get('page',-1)>=0):continue
                    label,target=next(targets)
                    rect=fitz.Rect(link['from'])
                    overlays.append('<a aria-label="'+html.escape(label,quote=True)+'" href="'+html.escape(target,quote=True)+'" style="position:absolute;z-index:10;display:block;left:'+str(rect.x0)+'pt;top:'+str(rect.y0)+'pt;width:'+str(rect.width)+'pt;height:'+str(rect.height)+'pt;cursor:pointer"></a>')
                end=page_html.rfind('</div>')
                page_html=page_html[:end]+''.join(overlays)+page_html[end:]
                pieces.append(f'<section id="page-{index+1}">'+page_html)
                links=conversion_links(page)
                if links:
                    pieces.append('<ul class="pdf-links">'+''.join('<li><a href="'+html.escape(target,quote=True)+'">'+html.escape(label)+'</a> — '+html.escape(target)+'</li>' for label,target in links)+'</ul>')
                pieces.append('</section>')
            pieces.append('</body></html>');result.write_text('\n'.join(pieces),encoding='utf-8');return
        texts=[]
        for page in doc:check_cancel();texts.append(page.get_text(sort=True))
        if not any(text.strip() for text in texts):raise ValueError('E_TEXT_EMPTY')
        if format=='txt':result.write_text('\n\f\n'.join(texts),encoding='utf-8');return
        # Standard OpenDocument text: editable paragraphs, explicit page breaks.
        paragraphs=[]
        for index,text in enumerate(texts):
            for line_index,line in enumerate(text.splitlines() or ['']):
                style='PageStart' if index and line_index==0 else 'Standard'
                if line_index==0:paragraphs.append(f'<text:p><text:bookmark text:name="page-{index+1}"/></text:p>')
                line_xml=escape(line)
                for label,target in conversion_links(doc[index]):
                    if label and label in line:
                        anchor='<text:a text:style-name="InternetLink" xlink:type="simple" xlink:href="'+escape(target,{'"':'&quot;'})+'">'+escape(label)+'</text:a>'
                        line_xml=line_xml.replace(escape(label),anchor,1)
                paragraphs.append(f'<text:p text:style-name="{style}">'+line_xml+'</text:p>')
            for label,target in conversion_links(doc[index]):
                paragraphs.append('<text:p><text:a text:style-name="InternetLink" xlink:type="simple" xlink:href="'+escape(target,{'"':'&quot;'})+'">'+escape(label)+'</text:a> — '+escape(target)+'</text:p>')
        content=('<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.2"><office:automatic-styles><style:style style:name="InternetLink" style:family="text"><style:text-properties fo:color="#0000ee" style:text-underline-style="solid" style:text-underline-width="auto" style:text-underline-color="font-color"/></style:style><style:style style:name="PageStart" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style></office:automatic-styles><office:body><office:text>'+''.join(paragraphs)+'</office:text></office:body></office:document-content>')
        manifest='<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'
        with zipfile.ZipFile(result,'w') as archive:
            archive.writestr('mimetype','application/vnd.oasis.opendocument.text',compress_type=zipfile.ZIP_STORED)
            archive.writestr('content.xml',content,compress_type=zipfile.ZIP_DEFLATED);archive.writestr('META-INF/manifest.xml',manifest,compress_type=zipfile.ZIP_DEFLATED)


def process(tool, inputs, output, options=None):
    previous=getattr(_job,'cancel',None)
    _job.cancel=(options or {}).get('cancel_event')
    try:
        check_cancel()
        return _process(tool,inputs,output,options)
    finally:_job.cancel=previous

def _process(tool, inputs, output, options=None):
    """Aktion synchron ausführen; GUI ruft diese Funktion in einem Worker auf."""
    options = options or {}
    if not (FUNCTION_BY_ID.get(tool) or Function(tool,'content',tool,'tool_dialog')).status(gui=False)[0]:
        raise RuntimeError('E_DEP')
    kind = BY_ID[tool][4]
    if (kind == 'one' and len(inputs)!=1) or (kind == 'two' and len(inputs)!=2) or (kind == 'many' and not inputs):
        raise ValueError('E_INPUT')
    paths = [Path(p).expanduser().resolve(strict=True) for p in inputs] if kind != 'url' else []
    if any(not p.is_file() for p in paths):
        raise ValueError('E_INPUT')
    if tool in ('image_resize','image_rotate','image_crop','text_search'):raise ValueError('E_IMAGE_GUI')
    if tool=='edit':
        if paths[0].suffix.lower()!='.pdf':raise ValueError('E_INPUT')
        subprocess.Popen(['libreoffice','--draw',str(paths[0])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return
    if tool=='document_info':return document_information(paths[0])
    if tool=='pdfa_check':return validate_pdfa(paths[0],flavour='0')
    destination = Path(output).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('E_EXISTS')
    suffix=conversion_suffix(options.get('convert_format','txt')) if tool=='convert' else '.txt' if tool=='text_extract' else '.zip' if tool in ZIP_TOOLS else '.pdf'
    if destination.suffix.lower() != suffix:
        raise ValueError('E_INPUT')
    with tempfile.TemporaryDirectory(prefix='.mintpdf-', dir=destination.parent) as temp:
        folder = Path(temp)
        result = folder / ('result'+suffix)
        if tool == 'text_extract':
            import pymupdf as fitz
            with fitz.open(paths[0]) as doc:
                if doc.needs_pass:raise ValueError('E_PASSWORD')
                if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
                text='\n\f\n'.join(page.get_text(sort=True) for page in doc)
                if not text.strip():raise ValueError('E_TEXT_EMPTY')
                result.write_text(text,encoding='utf-8')
        elif tool == 'crop':
            crop_pdf(paths[0],result,options.get('crop_rectangles',{}))
        elif tool == 'optimize':
            optimize_document(paths[0],result,options)
        elif tool == 'decrypt':
            if options.get('decrypt_method')=='password' and not options.get('password'):raise ValueError('E_PASSWORD')
            decrypt_pdf(paths[0],result,options.get('password',''))
        elif tool == 'form':
            create_form(paths[0],result)
        elif tool == 'pdfa':
            create_pdfa(paths[0],result,folder)
            validate_pdfa(result)
        elif tool == 'compress':
            run_command(processing_command(tool,paths[0],result,options))
        elif tool == 'ocr':
            command=processing_command(tool,paths[0],result,options)
            if not set(options.get('ocr_language','eng').split('+')).issubset(ocr_languages()): raise ValueError('E_OCR_LANGUAGE')
            if options.get('ocr_output','pdf')=='pdfa' and not shutil.which('gs'): raise RuntimeError('E_DEP')
            run_command(command)
        elif tool == 'web':
            source=paths[0]
            if source.suffix.lower() not in ('.html','.htm'):raise ValueError('E_INPUT')
            run_command(['wkhtmltopdf','--disable-javascript','--disable-local-file-access','--allow',str(source.parent),str(source),str(result)])
        elif tool == 'convert':
            convert_pdf(paths[0],result,options)
        else:
            _pdf_process(tool, paths, result, folder, options)
        if not result.is_file() or result.stat().st_size == 0:
            raise RuntimeError('E_TOOL')
        # link() ist atomar und verweigert vorhandene Ziele, auch bei Rennen.
        check_cancel()
        os.link(result, destination)


def prepare_pdfa_source(source, folder):
    """Normalize RGB overprint and print flags on a private copy, retaining links."""
    import pymupdf as fitz
    target=folder/'prepared.pdf'
    try:document=fitz.open(source)
    except fitz.FileDataError as exc:raise ValueError('E_INPUT') from exc
    with document as doc:
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
        for xref in range(1,doc.xref_length()):
            check_cancel()
            if doc.xref_is_stream(xref):continue
            # OPM=1 is forbidden for our RGB PDF/A output. Set the standard mode
            # instead of asking Ghostscript to silently discard incompatible objects.
            if doc.xref_get_key(xref,'OPM')==('int','1'):
                doc.xref_set_key(xref,'OPM','0')
            if doc.xref_get_key(xref,'Type')==('name','/Annot') or doc.xref_get_key(xref,'Subtype')==('name','/Link'):
                kind,value=doc.xref_get_key(xref,'F')
                flags=int(value) if kind=='int' else 0
                doc.xref_set_key(xref,'F',str(flags|4))
        doc.save(target,deflate=True)
    return target


def create_pdfa(source, result, folder):
    """Create PDF/A-2b with an embedded RGB output intent; reject incompatibility."""
    profiles = (Path('/usr/share/color/icc/ghostscript/srgb.icc'),
                *sorted(Path('/usr/share/ghostscript').glob('*/iccprofiles/srgb.icc')))
    profile = next((p for p in profiles if p.is_file()), None)
    if profile is None:
        raise RuntimeError('E_PDFA_PROFILE')
    source=prepare_pdfa_source(source,folder)
    # Hex strings avoid PostScript escaping and preserve arbitrary path bytes.
    profile_hex = os.fsencode(profile).hex()
    definition = folder / 'pdfa.ps'
    definition.write_text("""%!
[/_objdef {icc_PDFA} /type /stream /OBJ pdfmark
[{icc_PDFA} << /N 3 >> /PUT pdfmark
[{icc_PDFA} <""" + profile_hex + """> (r) file /PUT pdfmark
[/_objdef {OutputIntent_PDFA} /type /dict /OBJ pdfmark
[{OutputIntent_PDFA} << /Type /OutputIntent /S /GTS_PDFA1
/DestOutputProfile {icc_PDFA} /OutputConditionIdentifier (sRGB) >> /PUT pdfmark
[{Catalog} << /OutputIntents [{OutputIntent_PDFA}] >> /PUT pdfmark
""", encoding='ascii')
    run_command(['gs', '-dSAFER', '-dBATCH', '-dNOPAUSE', '-dPDFSTOPONERROR',
                 '-sDEVICE=pdfwrite', '-dPDFA=2', '-dPDFACompatibilityPolicy=2',
                 '-sColorConversionStrategy=RGB', '-dEmbedAllFonts=true',
                 '--permit-file-read=' + str(profile),
                 '-sOutputFile=' + str(result), str(definition), str(source)])


def validate_pdfa(source, flavour='2b'):
    """Require a complete veraPDF result against the explicit PDF/A-2b profile."""
    import xml.etree.ElementTree as ET
    command=validator_command()
    if not command:
        raise RuntimeError('E_PDFA_VALIDATOR')
    try:
        report=run_command([command,'--format','xml','--flavour',flavour,
                            str(Path(source).resolve())],capture=True,accepted_codes=(0,1))
        root=ET.fromstring(report)
        jobs=root.findall('./jobs/job')
        summary=root.find('batchSummary')
        if len(jobs)!=1 or summary is None or summary.get('totalJobs')!='1':
            raise ValueError('Incomplete validation report')
        if any(summary.get(key)!='0' for key in ('failedToParse','encrypted','outOfMemory','veraExceptions')):
            raise ValueError('Validator failed to process input')
        reports=jobs[0].findall('validationReport')
        if len(reports)!=1 or not re.fullmatch(r'PDF/A-(?:[123][abu]|4[ef]?) validation profile',reports[0].get('profileName','')) or (flavour!='0' and reports[0].get('profileName')!='PDF/A-'+flavour+' validation profile'):
            raise ValueError('Unexpected validation profile')
        result=reports[0]
        if result.get('isCompliant')=='false':
            import logging
            for rule in result.findall('./details/rule'):
                if rule.get('status')=='failed':
                    logging.warning('PDF/A: %s clause %s test %s: %s',
                                    rule.get('specification'),rule.get('clause'),
                                    rule.get('testNumber'),rule.findtext('description','').strip())
            raise RuntimeError('E_PDFA_INVALID')
        details=result.find('details')
        if result.get('isCompliant')!='true' or details is None or any(
                details.get(key)!='0' for key in ('failedRules','failedChecks')):
            raise ValueError('No successful validation result')
    except RuntimeError as exc:
        if str(exc) in ('E_CANCELLED','E_PDFA_INVALID'):raise
        raise RuntimeError('E_PDFA_VALIDATION') from exc
    except (ET.ParseError,ValueError,TypeError,OSError) as exc:
        raise RuntimeError('E_PDFA_VALIDATION') from exc
    return result.get('profileName').removesuffix(' validation profile')


def _pdf_process(tool, paths, result, folder, options):
    import pymupdf as fitz
    from contextlib import ExitStack
    with ExitStack() as stack:
        def opened(path):
            doc = stack.enter_context(fitz.open(stream=options["source_pdf"],filetype="pdf") if tool=="extract_images" and options.get("source_pdf") else fitz.open(path))
            if doc.needs_pass and not doc.authenticate(options.get('password','')):
                raise ValueError('E_PASSWORD')
            return doc
        out = stack.enter_context(fitz.open())
        if tool == 'create':
            text = options.get('text','')
            page = out.new_page()
            if page.insert_textbox(fitz.Rect(50,50,545,792),text,fontsize=12) < 0:
                raise ValueError('E_INPUT')
        elif tool == 'images_pdf' and options.get('placements') is not None:
            data=images_layout_pdf(options.get('image_sources') or [p.read_bytes() for p in paths],options['placements'],options.get('base_pdf'),options.get('image_pages'),options.get('image_rotations'))
            layout=stack.enter_context(fitz.open(stream=data,filetype='pdf'))
            out.insert_pdf(layout,widgets=True)
            out.set_metadata(layout.metadata);out.set_toc(layout.get_toc())
        elif tool == 'images_pdf':
            for path in paths:
                check_cancel()
                img = opened(path)
                pdf = stack.enter_context(fitz.open('pdf', img.convert_to_pdf()))
                out.insert_pdf(pdf)
        elif tool == 'merge':
            for path in paths:
                check_cancel()
                out.insert_pdf(opened(path))
        else:
            doc = opened(paths[0])
            if not doc.is_pdf or not doc.page_count:
                raise ValueError('E_INPUT')
            if tool in ('annotations','signature_image'):
                index=options.get('note_page',0)
                if type(index) is not int or not 0<=index<len(doc):raise ValueError('E_INPUT')
            if tool in ZIP_TOOLS:
                with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as archive:
                    if tool == 'split':
                        groups=split_groups(len(doc),options)
                        for i,group in enumerate(groups,1):
                            check_cancel()
                            with fitz.open() as single:
                                for page_number in group:
                                    check_cancel()
                                    single.insert_pdf(doc,from_page=page_number,to_page=page_number)
                                name=f'page-{group[0]+1:04}.pdf' if options.get('split_mode','single')=='single' else f'part-{i:04}.pdf'
                                archive.writestr(name,single.tobytes(garbage=4,deflate=True))
                    elif tool == 'pdf_images':
                        try: dpi=int(options.get('image_dpi','144'))
                        except (ValueError,TypeError) as exc: raise ValueError('E_OPTIONS') from exc
                        if dpi not in (72,144,150,300): raise ValueError('E_OPTIONS')
                        for i,page in enumerate(doc):
                            check_cancel()
                            archive.writestr(f'page-{i+1:04}.png',page.get_pixmap(dpi=dpi).tobytes('png'))
                    else:
                        requested=options.get('image_xrefs')
                        if requested is not None and (not isinstance(requested,(list,tuple)) or not requested or any(type(v) is not int for v in requested)):raise ValueError('E_INPUT')
                        wanted=set(requested) if requested is not None else None
                        seen=set();exported=set()
                        for page in doc:
                            check_cancel()
                            for image in page.get_images():
                                check_cancel()
                                xref=image[0]
                                if xref in seen: continue
                                seen.add(xref)
                                if wanted is not None and xref not in wanted:continue
                                data=doc.extract_image(xref);exported.add(xref)
                                archive.writestr(f'image-{xref}.{data["ext"]}',data['image'])
                        if not seen: raise ValueError('E_NO_IMAGES')
                        if wanted is not None and exported!=wanted:raise ValueError('E_INPUT')
                return
            if tool in ('overlay','compare'):
                second=opened(paths[1])
                if not second.is_pdf: raise ValueError('E_INPUT')
                if tool == 'overlay':
                    result.write_bytes(overlay_documents(paths[0].read_bytes(),paths[1].read_bytes(),options))
                    return
                else:
                    # Sichtvergleich: beide Originalseiten nebeneinander, A links/B rechts.
                    for i in range(max(len(doc),len(second))):
                        p=out.new_page(width=1190,height=842)
                        for j,src in enumerate((doc,second)):
                            if i<len(src): p.show_pdf_page(fitz.Rect(j*595,24,(j+1)*595,842),src,i)
                        p.insert_text((16,16),f'A  |  {i+1}',fontsize=10)
                        p.insert_text((611,16),f'B  |  {i+1}',fontsize=10)
            else:
                out.insert_pdf(doc)
                selected=pages(options.get('pages',''),len(out))
                if tool in ('extract','sort'): out.select(selected)
                elif tool == 'delete':
                    remaining=[i for i in range(len(out)) if i not in selected]
                    if not remaining: raise ValueError('E_INPUT')
                    out.select(remaining)
                elif tool == 'rotate':
                    angle=int(options.get('angle','90'))
                    if angle not in (90,180,270): raise ValueError('E_INPUT')
                    for i in selected: out[i].set_rotation((out[i].rotation+angle)%360)
                elif tool in ('watermark','numbers','redact','annotations','signature_image'):
                    text=options.get('text','').strip()
                    if tool not in ('numbers','signature_image') and not text: raise ValueError('E_INPUT')
                    matches=0
                    for i,page in enumerate(out):
                        check_cancel()
                        if tool=='signature_image':
                            if i==options.get('note_page',0):apply_signature(page,options['signature_bytes'],options)
                        elif tool=='annotations':
                            if i==int(options.get('note_page',0)):apply_annotation(page,text,options)
                        elif tool=='numbers': apply_page_number(page,i,options)
                        elif tool=='watermark':
                            apply_watermark(page,text,options)
                        else:
                            for rect in page.search_for(text):
                                check_cancel()
                                page.add_redact_annot(rect,fill=(0,0,0)); matches+=1
                            page.apply_redactions()
                    if tool in ('redact','compare','crop'):
                        if not matches: raise ValueError('E_NO_MATCH')
                        out.set_metadata({})
                        out.del_xml_metadata()
        kwargs=dict(garbage=4,deflate=True)
        if tool=='encrypt':
            password=options.get('password','')
            if not password: raise ValueError('E_PASSWORD')
            kwargs.update(encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw=password,user_pw=password)
        out.save(result,**kwargs)


# Formularanalyse und -erstellung (bisher forms.py), GPL-3.0-only.
def _form_opened(path):
    from pathlib import Path
    import re
    import math
    import pymupdf as fitz
    doc = fitz.open(path)
    if doc.needs_pass:
        doc.close()
        raise ValueError('E_PASSWORD')
    if not doc.is_pdf or not len(doc):
        doc.close()
        raise ValueError('E_INPUT')
    return doc

def _form_candidates(page):
    from pathlib import Path
    import re
    import math
    import pymupdf as fitz
    fields = []
    words = page.get_text('words')
    bounds = page.rect * page.derotation_matrix

    def add(kind, rect):
        r = fitz.Rect(rect)
        if r.is_empty or not bounds.contains(r):
            return
        if any((r.intersects(fitz.Rect(f['rect'])) for f in fields)):
            return
        fields.append({'kind': kind, 'rect': tuple(r)})

    def label_near(r, colon=False):
        for w in words:
            text = w[4].strip()
            box = fitz.Rect(w[:4])
            if len(text) < 2 or not any((c.isalpha() for c in text)):
                continue
            if colon and (not text.endswith(':')):
                continue
            cy = (box.y0 + box.y1) / 2
            ry = (r.y0 + r.y1) / 2
            if abs(cy - ry) < 10 and 0 <= r.x0 - box.x1 < 110:
                return True
            if colon and 0 <= r.y0 - box.y1 < 22 and (r.x0 - 10 <= box.x0 <= r.x1):
                return True
        return False
    for drawing in page.get_drawings():
        check_cancel()
        for item in drawing['items']:
            if item[0] == 're':
                r = fitz.Rect(item[1])
                if 5 <= r.width <= 22 and 5 <= r.height <= 22 and (0.65 <= r.width / r.height <= 1.5) and label_near(r):
                    add('checkbox', r)
                elif r.width >= 60 and 12 <= r.height <= 36 and label_near(r, True):
                    add('text', r)
            elif item[0] == 'l':
                a, b = item[1:3]
                if abs(a.y - b.y) < 0.5 and abs(a.x - b.x) >= 60:
                    r = fitz.Rect(min(a.x, b.x), a.y - 13, max(a.x, b.x), a.y + 1)
                    if label_near(r, True):
                        add('text', r)
    for block in page.get_text('rawdict', flags=fitz.TEXT_PRESERVE_WHITESPACE)['blocks']:
        check_cancel()
        if block['type'] != 0:
            continue
        for line in block['lines']:
            if tuple(line['dir']) != (1.0, 0.0):
                continue
            chars = [c for span in line['spans'] for c in span['chars']]
            text = ''.join((c['c'] for c in chars))
            for match in re.finditer('[._…]{4,}', text):
                group = chars[match.start():match.end()]
                r = fitz.Rect(group[0]['bbox'])
                for c in group[1:]:
                    r |= fitz.Rect(c['bbox'])
                if r.width >= 30:
                    baseline = group[0]['origin'][1]
                    r.y1 = baseline + 1
                    r.y0 = min(r.y0, baseline - 13)
                    add('text', r)
    return fields

def analyse_form(path):
    """Ergebnis enthält nur sichere Kandidaten und keine Patientendaten."""
    from pathlib import Path
    import re
    import math
    import pymupdf as fitz
    with _form_opened(path) as doc:
        existing = [(i, w.field_type) for i, p in enumerate(doc) for w in p.widgets() or []]
        if existing:
            if not doc.is_form_pdf:
                raise ValueError('E_FORM_INVALID')
            return dict(mode='existing', pages=len(doc), existing=len(existing), text=sum((t == fitz.PDF_WIDGET_TYPE_TEXT for _, t in existing)), checkbox=sum((t in (fitz.PDF_WIDGET_TYPE_CHECKBOX, fitz.PDF_WIDGET_TYPE_RADIOBUTTON) for _, t in existing)), fields=[], unrecognized=[])
        fields = []
        unrecognized = []
        for i, page in enumerate(doc):
            check_cancel()
            candidates = _form_candidates(page)
            for f in candidates:
                f['page'] = i
            fields.extend(candidates)
            if not candidates:
                unrecognized.append(i + 1)
        return dict(mode='detected' if fields else 'none', pages=len(doc), existing=0, text=sum((f['kind'] == 'text' for f in fields)), checkbox=sum((f['kind'] == 'checkbox' for f in fields)), fields=fields, unrecognized=unrecognized)

def create_form(source, destination):
    """In neues Ziel schreiben; ein vorhandenes Ziel niemals überschreiben."""
    from pathlib import Path
    import re
    import math
    import pymupdf as fitz
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise ValueError('E_EXISTS')
    report = analyse_form(source)
    if report['mode'] == 'none':
        raise ValueError('E_FORM_NONE')
    with _form_opened(source) as doc:
        for index, item in enumerate(report['fields'], 1):
            page = doc[item['page']]
            widget = fitz.Widget()
            widget.field_name = f'mintpdf_p{item['page'] + 1}_{index:03}'
            widget.field_label = widget.field_name
            widget.rect = fitz.Rect(item['rect'])
            widget.fill_color = None
            widget.border_width = 0
            widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT if item['kind'] == 'text' else fitz.PDF_WIDGET_TYPE_CHECKBOX
            widget.text_font = 'Helv' if item['kind'] == 'text' else 'ZaDb'
            widget.text_fontsize = 0
            widget.text_color = (0, 0, 0)
            widget.field_value = '' if item['kind'] == 'text' else 'Off'
            page.add_widget(widget)
        if report['mode'] == 'existing':
            data = Path(source).read_bytes()
        else:
            data = doc.tobytes(garbage=4, deflate=True)
    with target.open('xb') as stream:
        stream.write(data)
    return report

# PDF-Optimierung (bisher optimization.py), GPL-3.0-only.
def analyse_optimization(path):
    from pathlib import Path
    import re
    import pymupdf as fitz
    with fitz.open(path) as doc:
        if not doc.is_pdf:
            raise ValueError('E_INPUT')
        if doc.needs_pass:
            raise ValueError('E_PASSWORD')
        images = set()
        fonts = {}
        widgets = 0
        annotations = 0
        for page in doc:
            check_cancel()
            images.update((i[0] for i in page.get_images()))
            for font in page.get_fonts():
                check_cancel()
                fonts[font[0]] = font
            widgets += len(list(page.widgets() or []))
            annotations += len(list(page.annots() or []))
        uncompressed = sum((doc.xref_is_stream(x) and doc.xref_get_key(x, 'Filter')[0] == 'null' for x in range(1, doc.xref_length())))
        full_fonts = sum((f[1] != 'n/a' and (not re.match('^[A-Z]{6}\\+', f[3])) for f in fonts.values()))
        metadata = any((doc.metadata.get(k) for k in ('title', 'author', 'subject', 'keywords', 'creator', 'producer', 'creationDate', 'modDate'))) or bool(doc.get_xml_metadata())
        return dict(pages=len(doc), size=Path(path).stat().st_size / 1048576, images=len(images), fonts=len(fonts), embedded_fonts=sum((f[1] != 'n/a' for f in fonts.values())), full_fonts=full_fonts, widgets=widgets, annotations=annotations, attachments=doc.embfile_count(), uncompressed=uncompressed, metadata=bool(metadata))

def optimize_document(source, destination, options):
    from pathlib import Path
    import re
    import pymupdf as fitz
    try:
        level = int(options.get('opt_structure', '4'))
    except (ValueError, TypeError):
        raise ValueError('E_OPTIONS') from None
    if level not in (0, 1, 3, 4):
        raise ValueError('E_OPTIONS')
    with fitz.open(source) as doc:
        if not doc.is_pdf:
            raise ValueError('E_INPUT')
        if doc.needs_pass:
            raise ValueError('E_PASSWORD')
        if options.get('opt_metadata', False):
            doc.set_metadata({})
            doc.del_xml_metadata()
        if options.get('opt_attachments', False):
            for name in doc.embfile_names():
                doc.embfile_del(name)
        if options.get('opt_fonts', False):
            doc.subset_fonts()
        doc.save(destination, garbage=level, deflate=bool(options.get('opt_compress', True)), deflate_images=bool(options.get('opt_images', True)), deflate_fonts=bool(options.get('opt_font_compress', True)), encryption=fitz.PDF_ENCRYPT_KEEP)

# PDF-Vergleich ohne GUI (bisher comparison.py), GPL-3.0-only.
COMPARISON_MODES=('auto','text','visual','technical','both')
def comparison_raster(page):
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    return page.get_pixmap(dpi=96, colorspace=fitz.csRGB, alpha=False)

def comparison_technical(page):
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    return {'size': list(page.rect), 'rotation': page.rotation, 'crop': list(page.cropbox), 'fonts': sorted((str(f[1:]) for f in page.get_fonts())), 'images': len(page.get_images()), 'links': sorted((str({k: v for k, v in l.items() if k not in ('xref', 'id')}) for l in page.get_links())), 'fields': sorted((str((w.field_name, w.field_type, w.field_value, tuple(w.rect))) for w in page.widgets() or [])), 'annotations': sorted((str((a.type, a.info, tuple(a.rect))) for a in page.annots() or []))}

def comparison_regions(a, b):
    """Rasterzellen bündeln; geringfügige Farbabweichungen bis 12 ignorieren."""
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    w = max(a.width, b.width)
    h = max(a.height, b.height)
    sa = a.samples
    sb = b.samples
    cells = set()
    step = 24
    for y in range(h):
        if a.width == b.width and y < a.height and (y < b.height) and (sa[y * a.stride:(y + 1) * a.stride] == sb[y * b.stride:(y + 1) * b.stride]):
            continue
        for x in range(w):
            if x >= a.width or y >= a.height or x >= b.width or (y >= b.height):
                changed = True
            else:
                ia = y * a.stride + x * 3
                ib = y * b.stride + x * 3
                changed = any((abs(sa[ia + c] - sb[ib + c]) > 12 for c in range(3)))
            if changed:
                cells.add((x // step, y // step))
    boxes = []
    while cells:
        seed = cells.pop()
        todo = [seed]
        group = [seed]
        while todo:
            x, y = todo.pop()
            for n in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if n in cells:
                    cells.remove(n)
                    todo.append(n)
                    group.append(n)
        boxes.append((min((x for x, y in group)) * step, min((y for x, y in group)) * step, min(w, (max((x for x, y in group)) + 1) * step), min(h, (max((y for x, y in group)) + 1) * step)))
    return boxes

def compare_documents(first, second, mode='auto'):
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    if mode not in COMPARISON_MODES:
        raise ValueError('E_OPTIONS')
    sources = [Path(p).read_bytes() for p in (first, second)]
    with ExitStack() as stack:
        docs = [stack.enter_context(fitz.open(stream=s, filetype='pdf')) for s in sources]
        for d in docs:
            if d.needs_pass:
                raise ValueError('E_PASSWORD')
            if not d.is_pdf or not len(d):
                raise ValueError('E_INPUT')
        texts = [[p.get_text(sort=True) for p in d] for d in docs]
        mode = ('both' if any((t.strip() for ts in texts for t in ts)) else 'visual') if mode == 'auto' else mode
        signatures = []
        for d, ts in zip(docs, texts):
            signatures.append([(hashlib.sha256(comparison_raster(p).samples).hexdigest(), tuple(p.rect), ts[i]) for i, p in enumerate(d)])
        pairs = []
        for tag, a, z, b, y in SequenceMatcher(None, *signatures, autojunk=False).get_opcodes():
            if tag != 'replace':
                for k in range(max(z - a, y - b)):
                    pairs.append((a + k if a + k < z else None, b + k if b + k < y else None))
                continue
            m, n = (z - a, y - b)
            cost = [[0.0] * (n + 1) for _ in range(m + 1)]
            back = {}
            for x in range(1, m + 1):
                cost[x][0] = x * 0.6
                back[x, 0] = 'del'
            for q in range(1, n + 1):
                cost[0][q] = q * 0.6
                back[0, q] = 'add'
            for x in range(1, m + 1):
                for q in range(1, n + 1):
                    ta = texts[0][a + x - 1]
                    tb = texts[1][b + q - 1]
                    similarity = SequenceMatcher(None, ta, tb, autojunk=False).ratio() if ta.strip() or tb.strip() else 0
                    cost[x][q], back[x, q] = min((cost[x - 1][q - 1] + 1 - similarity, 'pair'), (cost[x - 1][q] + 0.6, 'del'), (cost[x][q - 1] + 0.6, 'add'))
            x, q = (m, n)
            part = []
            while x or q:
                action = back[x, q]
                if action == 'pair':
                    part.append((a + x - 1, b + q - 1))
                    x -= 1
                    q -= 1
                elif action == 'del':
                    part.append((a + x - 1, None))
                    x -= 1
                else:
                    part.append((None, b + q - 1))
                    q -= 1
            pairs.extend(reversed(part))
        rows = []
        text_count = visual_count = changed = 0
        for i, j in pairs:
            row = {'a': i, 'b': j, 'text': [], 'regions': [], 'technical': [], 'text_regions': [[], []], 'changed': False}
            if i is None or j is None:
                rows.append(row)
                continue
            if mode in ('text', 'both'):
                wa = texts[0][i].split()
                wb = texts[1][j].split()
                row['text'] = [(' '.join(wa[a:z]), ' '.join(wb[b:y])) for tag, a, z, b, y in SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes() if tag != 'equal']
            if mode == 'text':
                for n, index in enumerate((i, j)):
                    page = docs[n][index]
                    for change in row['text']:
                        if change[n]:
                            for rect in page.search_for(change[n]):
                                check_cancel()
                                row['text_regions'][n].append(tuple(rect * page.rotation_matrix * fitz.Matrix(96 / 72, 96 / 72)))
            if mode in ('visual', 'both'):
                if signatures[0][i][:2] != signatures[1][j][:2]:
                    row['regions'] = comparison_regions(comparison_raster(docs[0][i]), comparison_raster(docs[1][j]))
            if mode == 'technical':
                ta, tb = (comparison_technical(docs[0][i]), comparison_technical(docs[1][j]))
                row['technical'] = [(k, str(ta[k]), str(tb[k])) for k in ta if ta[k] != tb[k]]
            row['changed'] = bool(row['text'] or row['regions'] or row['technical'])
            changed += row['changed']
            text_count += len(row['text'])
            visual_count += len(row['regions'])
            rows.append(row)
        doc_changes = []
        if mode == 'technical':
            attrs = [{'metadata': d.metadata, 'bookmarks': d.get_toc(), 'attachments': [(n, hashlib.sha256(d.embfile_get(n)).hexdigest()) for n in d.embfile_names()], 'permissions': d.permissions, 'xml': d.get_xml_metadata()} for d in docs]
            doc_changes = [(k, str(attrs[0][k]), str(attrs[1][k])) for k in attrs[0] if attrs[0][k] != attrs[1][k]]
        return dict(sources=sources, rows=rows, mode=mode, pages1=len(docs[0]), pages2=len(docs[1]), changed=changed, added=sum((i is None for i, j in pairs)), deleted=sum((j is None for i, j in pairs)), text_count=text_count if mode in ('text', 'both') else None, visual_count=visual_count if mode in ('visual', 'both') else None, doc_changes=doc_changes)

def comparison_report(result, tr):
    from pathlib import Path
    from difflib import SequenceMatcher
    from contextlib import ExitStack
    import hashlib, logging, threading, io
    import pymupdf as fitz
    lines = [tr('cmp_summary').format(**{**result, 'text_count': result['text_count'] if result['text_count'] is not None else tr('cmp_unchecked'), 'visual_count': result['visual_count'] if result['visual_count'] is not None else tr('cmp_unchecked')}), tr('cmp_method')]
    for row in result['rows']:
        a = '—' if row['a'] is None else str(row['a'] + 1)
        b = '—' if row['b'] is None else str(row['b'] + 1)
        lines.append(f'\nPDF 1: {a} | PDF 2: {b}')
        if row['a'] is None:
            lines.append(tr('cmp_added'))
        elif row['b'] is None:
            lines.append(tr('cmp_deleted'))
        elif not row['changed']:
            lines.append(tr('cmp_unchanged'))
        for old, new in row['text']:
            lines.extend(['− ' + old, '+ ' + new])
        for box in row['regions']:
            lines.append(tr('cmp_region') + ' ' + str(box))
        for key, old, new in row['technical']:
            lines.extend([key, '− ' + old, '+ ' + new])
    for key, old, new in result['doc_changes']:
        lines.extend(['\n' + key, '− ' + old, '+ ' + new])
    return '\n'.join(lines)

# Sichere visuelle Schwärzung (bisher redaction.py), GPL-3.0-only.
def redact_regions(source, target, regions):
    from pathlib import Path
    import io, os, tempfile, logging
    import pymupdf as fitz
    target = Path(target).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise ValueError('E_EXISTS')
    if target.suffix.lower() != '.pdf' or not regions:
        raise ValueError('E_REDACT_AREA')
    with fitz.open(stream=source, filetype='pdf') if isinstance(source, bytes) else fitz.open(source) as doc:
        if doc.needs_pass:
            raise ValueError('E_PASSWORD')
        if not doc.is_pdf:
            raise ValueError('E_INPUT')
        for index, rect in regions:
            if index < 0 or index >= len(doc):
                raise ValueError('E_REDACT_AREA')
            page = doc[index]
            r = fitz.Rect(rect)
            if r.is_empty or r.is_infinite or (not (page.rect * page.derotation_matrix).contains(r)):
                raise ValueError('E_REDACT_AREA')
        for index, page in enumerate(doc):
            check_cancel()
            areas = [fitz.Rect(r) for i, r in regions if i == index]
            if not areas:
                continue
            for annot in list(page.annots() or []):
                check_cancel()
                if annot.type[0] == fitz.PDF_ANNOT_REDACT or any((annot.rect.intersects(r) for r in areas)):
                    page.delete_annot(annot)
            for widget in list(page.widgets() or []):
                check_cancel()
                if any((widget.rect.intersects(r) for r in areas)):
                    page.delete_widget(widget)
            for r in areas:
                page.add_redact_annot(r, fill=(0, 0, 0), cross_out=False)
            page.apply_redactions(images=2, graphics=2, text=0)
        doc.set_metadata({})
        doc.del_xml_metadata()
        for name in doc.embfile_names():
            doc.embfile_del(name)
        with tempfile.TemporaryDirectory(prefix='.mintpdf-redact-', dir=target.parent) as tmp:
            result = Path(tmp) / 'result.pdf'
            doc.save(result, garbage=4, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
            os.link(result, target)


def inspect_tool(tool):
    """Nur lesend prüfen; Versionsermittlung mit begrenzter Laufzeit."""
    import importlib.metadata
    import platform
    result=dict(tool,available=False,version='',error='')
    try:
        kind=tool['kind']
        if kind=='python':result.update(available=True,version=platform.python_version())
        elif kind=='gtk':
            import gi
            gi.require_version('Gtk','4.0')
            from gi.repository import Gtk
            result.update(available=True,version='.'.join(map(str,(Gtk.get_major_version(),Gtk.get_minor_version(),Gtk.get_micro_version()))))
        elif kind=='cairo':
            import cairo,gi
            gi.require_foreign('cairo')
            result.update(available=True,version=cairo.cairo_version_string())
        elif kind=='module':
            import importlib
            module=importlib.import_module(tool['module'])
            result['available']=True
            try:result['version']=importlib.metadata.version(tool.get('distribution',tool['module']))
            except importlib.metadata.PackageNotFoundError:result['version']=str(getattr(module,'__version__',''))
        elif kind=='command':
            command=validator_command() if tool['command']=='verapdf' else shutil.which(tool['command'])
            if command:
                result['available']=True
                proc=subprocess.run([command,*tool.get('version_args',['--version'])],capture_output=True,text=True,timeout=5,check=False)
                lines=(proc.stdout or proc.stderr).splitlines()
                if proc.returncode==0 and lines:result['version']=lines[0][:500]
                else:result['error']='info_version_unknown'
    except subprocess.TimeoutExpired:
        result['error']='info_timeout'
    except (OSError,ValueError,ImportError,subprocess.SubprocessError) as exc:
        result['error']='info_check_failed'
    return result


def crop_pdf(source,target,rectangles):
    """Sichtbaren Seitenbereich proportional zuschneiden; Original unverändert."""
    import pymupdf as fitz
    import math
    if not isinstance(rectangles,dict) or not rectangles:raise ValueError('E_INPUT')
    target=Path(target).expanduser().absolute()
    if target.exists() or target.is_symlink():raise FileExistsError('E_EXISTS')
    with (fitz.open(stream=source,filetype='pdf') if isinstance(source,(bytes,bytearray)) else fitz.open(source)) as doc:
        if not doc.is_pdf or not len(doc):raise ValueError('E_INPUT')
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        for index,values in rectangles.items():
            if type(index) is not int or not 0<=index<len(doc):raise ValueError('E_INPUT')
            if not isinstance(values,(list,tuple)) or len(values)!=4:raise ValueError('E_INPUT')
            if any(type(x) not in (int,float) or not math.isfinite(x) for x in values):raise ValueError('E_INPUT')
            x0,y0,x1,y1=values
            if not (0<=x0<x1<=1 and 0<=y0<y1<=1):raise ValueError('E_INPUT')
            page=doc[index];visible=page.rect
            rectangle=fitz.Rect(x0*visible.width,y0*visible.height,x1*visible.width,y1*visible.height)*page.derotation_matrix
            origin=page.cropbox.tl
            rectangle+=fitz.Rect(origin.x,origin.y,origin.x,origin.y)
            page.set_cropbox(rectangle)
        with tempfile.TemporaryDirectory(prefix='.mintpdf-crop-',dir=target.parent) as tmp:
            result=Path(tmp)/'result.pdf'
            doc.save(result,garbage=4,deflate=True,encryption=fitz.PDF_ENCRYPT_KEEP)
            os.link(result,target)


def images_layout_pdf(sources, placements, base_pdf=None, image_pages=None, rotations=None):
    """Vorschau und Export verwenden dieselbe Seitengeometrie (Punkte)."""
    import pymupdf as fitz
    import math
    if not sources or len(sources)!=len(placements):raise ValueError('E_INPUT')
    with (fitz.open(stream=base_pdf,filetype="pdf") if base_pdf else fitz.open()) as out:
        if out.needs_pass:raise ValueError("E_PASSWORD")
        if base_pdf and (not image_pages or len(image_pages)!=len(sources)):raise ValueError("E_INPUT")
        for index,(source,layout) in enumerate(zip(sources,placements)):
            if len(layout)!=6 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in layout):raise ValueError('E_INPUT')
            pw,ph,x,y,w,h=layout
            if pw<=0 or ph<=0 or w<=0 or h<=0 or x<0 or y<0 or x+w>pw+.001 or y+h>ph+.001:raise ValueError('E_INPUT')
            if base_pdf:
                number=image_pages[index]
                if not isinstance(number,int) or not 0<=number<len(out):raise ValueError("E_INPUT")
                page=out[number]
                if abs(page.rect.width-pw)>.01 or abs(page.rect.height-ph)>.01:raise ValueError("E_INPUT")
            else:page=out.new_page(width=pw,height=ph)
            rect=fitz.Rect(x,y,x+w,y+h)*page.derotation_matrix
            angle=rotations[index] if rotations is not None else 0
            if angle not in (0,90,180,270):raise ValueError('E_INPUT')
            page.insert_image(rect,stream=source,keep_proportion=True,rotate=(page.rotation+angle)%360)
        return out.tobytes(garbage=4,deflate=True)


def pdf_image_choices(source):
    """Eingebettete Bildobjekte eindeutig mit Seitenfundstellen und Vorschau auflisten."""
    import pymupdf as fitz
    with fitz.open(stream=source,filetype='pdf') as doc:
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        items={}
        for number,page in enumerate(doc,1):
            check_cancel()
            for image in page.get_images():
                check_cancel()
                xref=image[0]
                if xref in items:
                    if number not in items[xref]['pages']:items[xref]['pages'].append(number)
                    continue
                data=doc.extract_image(xref)
                pix=fitz.Pixmap(doc,xref)
                if pix.colorspace is None:pix=fitz.Pixmap(fitz.csRGB,pix)
                elif pix.colorspace.n>3:pix=fitz.Pixmap(fitz.csRGB,pix)
                while pix.width>240 or pix.height>180:pix.shrink(1)
                items[xref]={'xref':xref,'pages':[number],'width':data['width'],'height':data['height'],'ext':data['ext'],'preview':pix.tobytes('png')}
        if not items:raise ValueError('E_NO_IMAGES')
        return list(items.values())


def editable_pdf_images(source):
    """Bildplatzierungen für visuelle Bearbeitung, Text und Vektoren bleiben erhalten."""
    import pymupdf as fitz
    with fitz.open(stream=source,filetype='pdf') as doc:
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        sources=[];layouts=[];pages=[]
        for number,page in enumerate(doc):
            check_cancel()
            if any(a.type[0]==fitz.PDF_ANNOT_REDACT for a in page.annots() or []):raise ValueError('E_IMAGE_COMPLEX')
            images=page.get_image_info(xrefs=True)
            rects=[fitz.Rect(i['bbox']) for i in images]
            for n,item in enumerate(images):
                rect=rects[n];a,b,c,d,_,_=item['transform']
                if not item['xref'] or abs(b)>.01 or abs(c)>.01 or a<=0 or d<=0:raise ValueError('E_IMAGE_COMPLEX')
                if any(n!=j and (rect & other).get_area()>.01 for j,other in enumerate(rects)):raise ValueError('E_IMAGE_COMPLEX')
                visible=rect*page.rotation_matrix
                if not page.rect.contains(visible):raise ValueError('E_IMAGE_COMPLEX')
                pix=fitz.Pixmap(doc,item['xref'])
                data=doc.extract_image(item['xref']);mask=data.get('smask',0)
                if mask:pix=fitz.Pixmap(pix,fitz.Pixmap(doc,mask))
                if pix.colorspace is None or pix.colorspace.n>3:pix=fitz.Pixmap(fitz.csRGB,pix)
                sources.append(pix.tobytes('png'));layouts.append([page.rect.width,page.rect.height,visible.x0,visible.y0,visible.width,visible.height]);pages.append(number)
            for rect in rects:page.add_redact_annot(rect,fill=False,cross_out=False)
            if rects:page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE,graphics=fitz.PDF_REDACT_LINE_ART_NONE,text=fitz.PDF_REDACT_TEXT_NONE)
        if not sources:raise ValueError('E_NO_IMAGES')
        return doc.tobytes(garbage=4,deflate=True),sources,layouts,pages


def crop_embedded_image(source,frame,rotation=0):
    """Bildpixel im sichtbaren gedrehten Koordinatensystem zuschneiden."""
    import pymupdf as fitz
    import math
    if len(frame)!=4 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in frame):raise ValueError('E_INPUT')
    x0,y0,x1,y1=frame
    if not (0<=x0<x1<=1 and 0<=y0<y1<=1) or rotation not in (0,90,180,270):raise ValueError('E_INPUT')
    pix=fitz.Pixmap(source)
    if pix.colorspace is None or pix.colorspace.n>3:pix=fitz.Pixmap(fitz.csRGB,pix)
    if rotation:
        with fitz.open() as doc:
            page=doc.new_page(width=pix.width,height=pix.height)
            page.insert_image(page.rect,stream=source);page.set_rotation((-rotation)%360)
            pix=page.get_pixmap(alpha=bool(pix.alpha))
    rect=fitz.IRect(max(0,int(x0*pix.width)),max(0,int(y0*pix.height)),min(pix.width,math.ceil(x1*pix.width)),min(pix.height,math.ceil(y1*pix.height)))
    clipped=fitz.Pixmap(pix.colorspace,rect,bool(pix.alpha));clipped.copy(pix,rect);clipped.set_origin(0,0)
    return clipped.tobytes('png')


def search_pdf_text(source,query):
    """Treffer je Seite und markierbare Textrechtecke; keine Änderung an der PDF."""
    import pymupdf as fitz
    if not isinstance(query,str) or not query.strip():raise ValueError('E_INPUT')
    results=[]
    with fitz.open(stream=source,filetype='pdf') as doc:
        if doc.needs_pass:raise ValueError('E_PASSWORD')
        for number,page in enumerate(doc):
            check_cancel()
            rects=page.search_for(query.strip())
            if rects:results.append({'page':number,'rects':[list(rect) for rect in rects]})
    return results
