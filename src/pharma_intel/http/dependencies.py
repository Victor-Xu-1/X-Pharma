from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from pharma_intel.db import get_session
from pharma_intel.security import Principal, require_principal

SessionDep = Annotated[Session, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(require_principal)]
