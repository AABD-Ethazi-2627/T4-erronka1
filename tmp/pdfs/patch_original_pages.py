from io import BytesIO
import re
import pdfplumber
from pypdf import PdfReader
from pypdf.generic import ContentStream, ByteStringObject, NameObject
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics

def font_map(font):
    if '/ToUnicode' not in font:return {}
    cm=font['/ToUnicode'].get_object().get_data().decode('latin1'); m={}
    for block in re.findall(r'beginbfchar(.*?)endbfchar',cm,re.S):
        for a,b in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',block):
            m[int(a,16)]=bytes.fromhex(b).decode('utf-16-be')
    for block in re.findall(r'beginbfrange(.*?)endbfrange',cm,re.S):
        for a,b,c in re.findall(r'<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>',block):
            for k in range(int(a,16),int(b,16)+1):m[k]=chr(int(c,16)+k-int(a,16))
    return m

def revise_original_pages(reader):
    # Business-case terminology only; the economic model still contains estimates.
    changes={
      4:[('simulagailu','Proiektuan, ARAKAINen CNC makinetatik jasotako datuak aztertzen dira, hala nola')],
      17:[('simulagailuak','Prozesadore honek ARAKAINen matxuren historikoko benetako informazioa ateratzen du.')],
      19:[('simulagailuak','Ebaluazioa ARAKAINek emandako benetako matxura-etiketetan oinarritzen da.')],
      29:[('simulazioan','Kostu horiek ARAKAINen kostu-eredurako erabilitako estimazioak dira.')],
      34:[('simulagailutik','Gainera, eredua ARAKAINen datu historikoekin entrenatzen da, eta CNC makinen uneko'),
          ('simulagailuko','datuak iragarpenak egiteko erabiltzen dira. Horregatik, produkzio-datuekin lortutako')],
      39:[('simulazioaren','Kostu horiek ARAKAINen kostu-eredurako estimazioak dira.')],
      40:[('Aurrezki simulatua','Aurrezki estimatua: Matxurak detektatzeari esker lor daitekeen aurrezkiaren')],
      41:[('simulatua','eta aurrezki estimatua kontsulta daitezke.')],
    }
    with pdfplumber.open(reader.stream) as pd:
        for idx,items in changes.items():
            page=reader.pages[idx]
            maps={key:font_map(v.get_object()) for key,v in page['/Resources']['/Font'].items()}
            st=ContentStream(page.get_contents(),reader)
            seq=''; positions=[]; current=None
            for opi,(args,op) in enumerate(st.operations):
                if op==b'Tf':current=str(args[0])
                if op==b'Tj':
                    obj=args[0]
                    raw=obj.original_bytes if hasattr(obj,'original_bytes') else bytes(obj)
                    mapping=maps.get(current,{})
                    text=''.join(mapping.get(int.from_bytes(raw[k:k+2],'big'),'?') for k in range(0,len(raw),2)) if mapping else raw.decode('latin1')
                    seq+=text;positions.extend([opi]*len(text))
            lines=pd.pages[idx].extract_text_lines()
            overlay=BytesIO(); c=canvas.Canvas(overlay,pagesize=tuple(map(float,[page.mediabox.width,page.mediabox.height])))
            for needle,new in items:
                matches=[line for line in lines if needle in line['text']]
                if len(matches)!=1:raise ValueError((idx,needle,len(matches)))
                line=matches[0]; text=line['text']
                pattern=r'\s*'.join(re.escape(t) for t in text.split())
                found=list(re.finditer(pattern,seq))
                if len(found)!=1:raise ValueError(('stream match',idx,text,len(found),seq[:150]))
                span=found[0].span()
                for opi in set(positions[span[0]:span[1]]):st.operations[opi][0][0]=ByteStringObject(b'')
                x=line['x0']; max_width=float(page.mediabox.width)-72-x
                new=new.removeprefix('● ')
                if text.startswith('●'):new='\u2022 '+new
                size=min(11,max_width/pdfmetrics.stringWidth(new,'Arial',1))
                c.setFont('Arial',size)
                baseline=float(page.mediabox.height)-line['bottom']+2.3
                c.drawString(x,baseline,new)
            c.save()
            page[NameObject('/Contents')]=st
            page.merge_page(PdfReader(overlay).pages[0])
            print('Amended source page',idx+1)
