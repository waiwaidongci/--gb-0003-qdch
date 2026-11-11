import csv,io
from fastapi.responses import Response
def csv_response(filename,rows,headers):
 out=io.StringIO();writer=csv.writer(out);writer.writerow(headers)
 for values in rows:
  writer.writerow([("'"+str(v)) if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values])
 return Response('﻿'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})
