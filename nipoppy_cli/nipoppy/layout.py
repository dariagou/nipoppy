"""Dataset layout."""

from functools import cached_property
from pathlib import Path
from typing import Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from nipoppy.base import Base
from nipoppy.utils import FPATH_DEFAULT_LAYOUT, get_pipeline_tag, load_json


class PathInfo(BaseModel):
    """Relative path and description for a directory or file."""

    _is_directory: bool
    _is_required: bool = True

    path: Path
    description: Optional[str] = None


class DpathInfo(PathInfo):
    """Relative path and description for a directory."""

    _is_directory = True


class FpathInfo(PathInfo):
    """Relative path and description for a file."""

    _is_directory = False


class OptionalFpathInfo(FpathInfo):
    """Relative path and description for a file that is optional."""

    _is_required = False


class LayoutConfig(BaseModel):
    """Relative paths for the dataset layout."""

    model_config = ConfigDict(extra="forbid")

    dpath_bids: DpathInfo
    dpath_derivatives: DpathInfo
    dpath_sourcedata: DpathInfo
    dpath_downloads: DpathInfo
    dpath_proc: DpathInfo
    dpath_releases: DpathInfo
    dpath_containers: DpathInfo
    dpath_descriptors: DpathInfo
    dpath_invocations: DpathInfo
    dpath_scripts: DpathInfo
    dpath_pybids: DpathInfo
    dpath_bids_db: DpathInfo
    dpath_bids_ignore_patterns: DpathInfo
    dpath_scratch: DpathInfo
    dpath_raw_dicom: DpathInfo
    dpath_logs: DpathInfo
    dpath_tabular: DpathInfo
    dpath_assessments: DpathInfo
    dpath_demographics: DpathInfo

    fpath_config: FpathInfo
    fpath_manifest: FpathInfo
    fpath_doughnut: OptionalFpathInfo
    fpath_imaging_bagel: OptionalFpathInfo

    @cached_property
    def path_labels(self) -> list[str]:
        """Return a list of all path labels defined in the layout."""
        return list(self.model_dump().keys())

    @cached_property
    def path_infos(self) -> list[PathInfo]:
        """Return a list of all PathInfo objects defined in the layout."""
        return [getattr(self, path_label) for path_label in self.path_labels]

    def get_path_info(self, path_label: str) -> PathInfo:
        """Return the PathInfo object associated with the given path label."""
        return getattr(self, path_label)


class DatasetLayout(Base):
    """File/directory structure for a specific dataset."""

    def __init__(
        self, dpath_root: Path | str, fpath_config: Optional[Path | str] = None
    ):
        """Initialize the object.

        Parameters
        ----------
        dataset_root: Path | str
            Path to the root directory of the dataset.
        fpath_config: Path | str | None
            Path to layout config to use, by default None.
            If None, the default layout will be used.
        """
        # use the default layout if none is specified
        if fpath_config is None:
            fpath_config = FPATH_DEFAULT_LAYOUT

        fpath_config = Path(fpath_config)
        if not fpath_config.exists():
            raise FileNotFoundError(f"Layout config file not found: {fpath_config}")

        # load the config
        config = LayoutConfig(**load_json(fpath_config))

        self.dpath_root = Path(dpath_root)
        self.fpath_spec = Path(fpath_config)
        self.config = config

        # directories (for type hinting)
        self.dpath_bids: Path
        self.dpath_derivatives: Path
        self.dpath_sourcedata: Path
        self.dpath_downloads: Path
        self.dpath_proc: Path
        self.dpath_releases: Path
        self.dpath_containers: Path
        self.dpath_descriptors: Path
        self.dpath_invocations: Path
        self.dpath_scripts: Path
        self.dpath_pybids: Path
        self.dpath_bids_db: Path
        self.dpath_bids_ignore_patterns: Path
        self.dpath_scratch: Path
        self.dpath_raw_dicom: Path
        self.dpath_logs: Path
        self.dpath_tabular: Path
        self.dpath_assessments: Path
        self.dpath_demographics: Path

        # files (for type hinting)
        self.fpath_config: Path
        self.fpath_doughnut: Path
        self.fpath_manifest: Path
        self.fpath_imaging_bagel: Path

        # directory names
        self.dname_pipeline_work = "work"
        self.dname_pipeline_output = "output"

    def get_full_path(self, path: str | Path) -> Path:
        """Build a full path from a relative path."""
        return self.dpath_root / path

    def __getattribute__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError as exception:
            if name in self.config.path_labels:
                return self.get_full_path(self.config.get_path_info(name).path)
            else:
                raise exception

    def get_paths(self, directory=True, include_optional=False) -> list[Path]:
        """Return a list of all directory or file paths."""
        paths = [
            self.get_full_path(path_info.path)
            for path_info in self.config.path_infos
            if directory == path_info._is_directory
            and (include_optional or path_info._is_required)
        ]
        return paths

    @cached_property
    def dpaths(self) -> list[Path]:
        """Return a list of all required directory paths."""
        return self.get_paths(directory=True)

    @cached_property
    def fpaths(self) -> list[Path]:
        """Return a list of all required file paths."""
        return self.get_paths(directory=False)

    @cached_property
    def dpath_descriptions(self) -> list[Tuple[Path, str]]:
        """Return a list of directory paths and associated description strings."""
        info_list = [
            (self.get_full_path(path_info.path), path_info.description)
            for path_info in self.config.path_infos
            if path_info._is_directory and path_info.description is not None
        ]
        return info_list

    def _find_missing_paths(self) -> list[Path]:
        """Return a list of missing paths."""
        missing = [dpath for dpath in self.dpaths if not dpath.exists()]
        for fpath in self.fpaths:
            if not fpath.exists():
                missing.append(fpath)
        return missing

    def validate(self) -> bool:
        """Validate that all the expected paths exist."""
        missing_paths = self._find_missing_paths()
        if len(missing_paths) != 0:
            raise FileNotFoundError(
                f"Missing {len(missing_paths)} paths"
                f": {[str(path) for path in missing_paths]}"
            )
        return True

    def get_dpath_pipeline(self, pipeline_name: str, pipeline_version: str) -> Path:
        """Return the path to a pipeline's directory."""
        return self.dpath_derivatives / pipeline_name / pipeline_version

    def get_dpath_pipeline_work(
        self,
        pipeline_name: str,
        pipeline_version: str,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ) -> Path:
        """Return the path to a pipeline's working directory."""
        return (
            self.get_dpath_pipeline(pipeline_name, pipeline_version)
            / self.dname_pipeline_work
            / get_pipeline_tag(
                pipeline_name,
                pipeline_version,
                participant=participant,
                session=session,
            )
        )

    def get_dpath_pipeline_output(
        self, pipeline_name: str, pipeline_version: str
    ) -> Path:
        """
        Return the path to a pipeline's working directory.

        Note: This path is the same given a pipeline name and version
        (i.e. does not depend on participant or session).
        """
        return (
            self.get_dpath_pipeline(pipeline_name, pipeline_version)
            / self.dname_pipeline_output
        )

    def get_dpath_bids_db(
        self,
        pipeline_name: str,
        pipeline_version: str,
        participant: Optional[str] = None,
        session: Optional[str] = None,
    ) -> Path:
        """Return the path to a pipeline's BIDS database directory."""
        dname = get_pipeline_tag(
            pipeline_name, pipeline_version, participant=participant, session=session
        )
        return self.dpath_bids_db / dname
