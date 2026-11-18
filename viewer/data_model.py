"""
data_model.py
imzML + multi-channel TIFF 파일 로드, 정규화, 채널 이미지 추출을 담당하는 데이터 레이어.

지원 포맷:
    imzML (Continuous / Processed 모드)  — pyimzml
    TIFF  (CYX / ZYX / YX 형식)          — tifffile
"""

from __future__ import annotations

import os
import numpy as np
from pyimzml.ImzMLParser import ImzMLParser


# 파일이 이 크기(바이트) 이하면 전체를 메모리에 올린다
FULL_LOAD_THRESHOLD = 500 * 1024 * 1024  # 500 MB


class MSIDataModel:
    """
    imzML + ibd 또는 멀티채널 TIFF 파일을 읽어
    이온 이미지 슬라이스 및 스펙트럼을 제공한다.

    속성:
        mz_array   : (N,) float64 – m/z 축 (빈닝 시 빈 중심값; TIFF는 채널 인덱스)
        shape      : (height, width) 픽셀 수
        n_channels : m/z 채널 수 (load-time 빈닝 후)
        mode       : 'continuous' | 'processed' | 'tiff'
        norm_mode  : 'none' | 'tic' | 'rms' | 'median'
    """

    def __init__(self):
        self._parser = None          # ImzMLParser 인스턴스 (lazy 모드용으로도 보관)
        self._cube = None            # (H, W, N) float32 – full-load 시 전체 데이터
        self._tic_map = None         # (H, W) – 각 픽셀의 TIC (정규화 계수 캐시)
        self._global_spectrum = None # (N,) – 전체 픽셀 합산 스펙트럼 캐시
        self._rms_map = None
        self._median_map = None
        self.mz_array = None
        self.shape = (0, 0)
        self.n_channels = 0
        self.mode = None
        self.norm_mode = "none"
        self._full_loaded = False
        # load-time binning 상태
        self._bin_da = 0.0
        self._bin_edges: np.ndarray | None = None   # lazy 모드 빈닝 조회용
        # TIFF 픽셀 크기 (nm)
        self._tiff_pixel_size_nm: float | None = None

    # ------------------------------------------------------------------ #
    #  정적 사전 스캔 (파일 열기 전 채널 수 추정)
    # ------------------------------------------------------------------ #

    @staticmethod
    def pre_scan(imzml_path: str) -> tuple[str, int, float, float]:
        """
        imzML 파일 열기 전 빠른 사전 스캔.

        반환: (mode, estimated_n_channels, mz_min, mz_max)
            continuous: 정확한 채널 수와 m/z 범위.
            processed:  첫 10 픽셀 샘플 기반 추정값 (실제보다 클 수 있음).
        """
        parser = ImzMLParser(imzml_path)

        # mode 판별
        if len(parser.coordinates) < 2:
            mode = "continuous"
        else:
            _, i0 = parser.getspectrum(0)
            _, i1 = parser.getspectrum(1)
            mode = "continuous" if len(i0) == len(i1) else "processed"

        if mode == "continuous":
            mzs, _ = parser.getspectrum(0)
            mzs = np.asarray(mzs, dtype=np.float64)
            mz_min = float(mzs[0]) if len(mzs) > 0 else 0.0
            mz_max = float(mzs[-1]) if len(mzs) > 0 else 0.0
            return mode, len(mzs), mz_min, mz_max

        # processed: 처음 최대 10픽셀 샘플링
        n_sample = min(10, len(parser.coordinates))
        sampled_mzs: set[float] = set()
        mz_min_val = float("inf")
        mz_max_val = float("-inf")
        for i in range(n_sample):
            mzs, _ = parser.getspectrum(i)
            mzs = np.asarray(mzs, dtype=np.float64)
            if len(mzs) > 0:
                sampled_mzs.update(float(m) for m in mzs)
                mz_min_val = min(mz_min_val, float(mzs[0]))
                mz_max_val = max(mz_max_val, float(mzs[-1]))

        n_unique = len(sampled_mzs)
        if n_unique < 2:
            m0 = mz_min_val if mz_min_val != float("inf") else 0.0
            m1 = mz_max_val if mz_max_val != float("-inf") else 0.0
            return mode, n_unique, m0, m1

        # 전체 픽셀 수 기반 sqrt 스케일 추정
        n_total = len(parser.coordinates)
        est = max(n_unique, int(n_unique * (n_total / n_sample) ** 0.5))
        m0 = mz_min_val if mz_min_val != float("inf") else 0.0
        m1 = mz_max_val if mz_max_val != float("-inf") else 0.0
        return mode, est, m0, m1

    # ------------------------------------------------------------------ #
    #  파일 로드 — imzML
    # ------------------------------------------------------------------ #

    def load(self, imzml_path: str, bin_da: float = 0.0) -> None:
        """
        .imzML 파일 경로를 받아 데이터를 로드한다.
        bin_da > 0 이면 load-time 스펙트럼 빈닝을 적용한다.
        """
        if not os.path.exists(imzml_path):
            raise FileNotFoundError(f"File not found: {imzml_path}")

        # 상태 초기화
        self._parser = None
        self._cube = None
        self._tic_map = None
        self._global_spectrum = None
        self._rms_map = None
        self._median_map = None
        self._tiff_pixel_size_nm = None

        parser = ImzMLParser(imzml_path)
        self._parser = parser
        self._bin_da = bin_da

        # 이미지 크기 (imzML은 1-based 좌표)
        max_x = max(c[0] for c in parser.coordinates)
        max_y = max(c[1] for c in parser.coordinates)
        self.shape = (max_y, max_x)

        self.mode = self._detect_mode(parser)
        self.norm_mode = "none"

        # 원시(raw) m/z 축 구성
        if self.mode == "continuous":
            raw_mzs, _ = parser.getspectrum(0)
            raw_mz = np.array(raw_mzs, dtype=np.float64)
        else:
            raw_mz = self._build_processed_mz_axis(parser)

        # load-time 빈닝 적용
        if bin_da > 0 and len(raw_mz) >= 2:
            mz_min = float(raw_mz[0])
            mz_max = float(raw_mz[-1])
            bin_edges = np.arange(mz_min, mz_max + bin_da, bin_da)
            if len(bin_edges) < 2 or bin_edges[-1] < mz_max:
                bin_edges = np.append(bin_edges, bin_edges[-1] + bin_da)
            self._bin_edges = bin_edges
            self.mz_array = (bin_edges[:-1] + bin_edges[1:]) / 2
        else:
            self._bin_edges = None
            self.mz_array = raw_mz
            raw_mz = None   # _full_load에 빈닝 불필요 신호

        self.n_channels = len(self.mz_array)

        # ibd 파일 크기로 full-load 여부 결정
        ibd_path = os.path.splitext(imzml_path)[0] + ".ibd"
        ibd_size = os.path.getsize(ibd_path) if os.path.exists(ibd_path) else 0

        if ibd_size <= FULL_LOAD_THRESHOLD:
            self._full_load(parser, raw_mz)
        else:
            self._full_loaded = False

        self._global_spectrum = None

    def _detect_mode(self, parser) -> str:
        if len(parser.coordinates) < 2:
            return "continuous"
        _, i0 = parser.getspectrum(0)
        _, i1 = parser.getspectrum(1)
        return "continuous" if len(i0) == len(i1) else "processed"

    def _build_processed_mz_axis(self, parser) -> np.ndarray:
        all_mzs: set = set()
        for i in range(len(parser.coordinates)):
            mzs, _ = parser.getspectrum(i)
            all_mzs.update(mzs)
        return np.array(sorted(all_mzs), dtype=np.float64)

    def _full_load(self, parser, raw_mz: np.ndarray | None = None) -> None:
        """
        전체 데이터를 (H, W, N) float32 큐브로 메모리에 적재한다.
        raw_mz가 주어지면 load-time 빈닝 경로를 사용한다.
        """
        H, W = self.shape
        N = self.n_channels
        cube = np.zeros((H, W, N), dtype=np.float32)

        if raw_mz is not None and self._bin_edges is not None:
            # ── Load-time 빈닝 경로 ──────────────────────────────────────
            bin_edges = self._bin_edges
            n_bins = N

            if self.mode == "continuous":
                # 공통 m/z 축에 대한 빈 할당 사전 계산
                raw_bin_idx = np.clip(
                    np.digitize(raw_mz, bin_edges) - 1, 0, n_bins - 1
                )
                bin_counts = np.bincount(raw_bin_idx, minlength=n_bins).astype(np.float32)
                bin_counts = np.where(bin_counts > 0, bin_counts, 1.0)

                for i, (x, y, *_) in enumerate(parser.coordinates):
                    _, intensities = parser.getspectrum(i)
                    row, col = y - 1, x - 1
                    binned = np.zeros(n_bins, dtype=np.float64)
                    np.add.at(binned, raw_bin_idx, np.asarray(intensities, dtype=np.float64))
                    cube[row, col, :] = (binned / bin_counts).astype(np.float32)

            else:
                # processed: 픽셀마다 m/z 배열이 다름
                for i, (x, y, *_) in enumerate(parser.coordinates):
                    mzs, intensities = parser.getspectrum(i)
                    row, col = y - 1, x - 1
                    pix_idx = np.clip(
                        np.digitize(mzs, bin_edges) - 1, 0, n_bins - 1
                    )
                    binned = np.zeros(n_bins, dtype=np.float64)
                    np.add.at(binned, pix_idx, np.asarray(intensities, dtype=np.float64))
                    counts_pix = np.bincount(pix_idx, minlength=n_bins).astype(np.float32)
                    safe = np.where(counts_pix > 0, counts_pix, 1.0)
                    cube[row, col, :] = (binned / safe).astype(np.float32)

        else:
            # ── 원본 로드 경로 ────────────────────────────────────────────
            for idx, (x, y, *_) in enumerate(parser.coordinates):
                mzs, intensities = parser.getspectrum(idx)
                row, col = y - 1, x - 1
                if self.mode == "continuous":
                    cube[row, col, :] = intensities
                else:
                    indices = np.searchsorted(self.mz_array, mzs)
                    indices = np.clip(indices, 0, N - 1)
                    cube[row, col, indices] = intensities

        self._cube = cube
        self._full_loaded = True
        self._compute_tic_map()

    # ------------------------------------------------------------------ #
    #  파일 로드 — TIFF
    # ------------------------------------------------------------------ #

    def load_tiff(self, tiff_path: str) -> None:
        """
        멀티채널 TIFF 파일을 로드한다.
        지원 형식: (C, H, W), (H, W, C), (H, W) — tifffile 자동 감지.
        """
        import tifffile  # 런타임 임포트 (선택적 의존성)

        # 상태 초기화
        self._parser = None
        self._bin_da = 0.0
        self._bin_edges = None
        self._global_spectrum = None
        self._tic_map = None
        self._rms_map = None
        self._median_map = None
        self._tiff_pixel_size_nm = None

        arr = tifffile.imread(tiff_path)

        # 싱글톤 차원 제거 후 3D로 정규화 → (C, H, W)
        arr = np.squeeze(arr)
        if arr.ndim == 2:
            arr = arr[np.newaxis, ...]      # 단일 채널 (1, H, W)
        elif arr.ndim == 4:
            arr = arr[0]                    # 첫 번째 Z/T 슬라이스
        if arr.ndim != 3:
            raise ValueError(
                f"Unsupported TIFF shape after squeeze: {arr.shape}. "
                "Expected 2D (H,W) or 3D (C,H,W) / (Z,H,W)."
            )

        # (C, H, W) → (H, W, C)
        self._cube = np.moveaxis(arr, 0, -1).astype(np.float32)
        H, W, C = self._cube.shape

        self.shape = (H, W)
        self.n_channels = C
        self.mz_array = np.arange(C, dtype=np.float64)   # 채널 인덱스
        self.mode = "tiff"
        self.norm_mode = "none"
        self._full_loaded = True

        # TIFF 메타데이터에서 픽셀 크기 읽기 (XResolution 태그)
        try:
            with tifffile.TiffFile(tiff_path) as tf:
                page = tf.pages[0]
                tags = page.tags
                xres_tag = tags.get("XResolution")
                unit_tag = tags.get("ResolutionUnit")
                if xres_tag is not None:
                    xres = xres_tag.value
                    if isinstance(xres, tuple) and len(xres) == 2 and xres[1] != 0:
                        xres = xres[0] / xres[1]
                    unit_val = int(unit_tag.value) if unit_tag is not None else 2
                    if float(xres) > 0:
                        # unit: 1=no-unit, 2=inch, 3=cm
                        if unit_val == 2:
                            um_per_px = 25400.0 / float(xres)   # 1 inch = 25400 µm
                        elif unit_val == 3:
                            um_per_px = 10000.0 / float(xres)
                        else:
                            um_per_px = None
                        if um_per_px is not None:
                            self._tiff_pixel_size_nm = um_per_px * 1000.0
        except Exception:
            pass

        self._compute_tic_map()

    # ------------------------------------------------------------------ #
    #  채널 이미지 반환
    # ------------------------------------------------------------------ #

    def get_channel_image(self, channel_idx: int) -> np.ndarray:
        """
        특정 채널(m/z 인덱스)의 이온 이미지 (H, W) float32를 반환한다.
        정규화 모드가 적용된 값이 반환된다.
        """
        channel_idx = int(np.clip(channel_idx, 0, self.n_channels - 1))

        if self._full_loaded:
            img = self._cube[:, :, channel_idx].copy()
        else:
            img = self._lazy_get_channel(channel_idx)

        return self._apply_normalization(img)

    def _lazy_get_channel(self, channel_idx: int) -> np.ndarray:
        """full-load 안 된 경우 픽셀 단위로 채널 이미지를 구성한다."""
        H, W = self.shape
        img = np.zeros((H, W), dtype=np.float32)

        if self._bin_edges is not None:
            # load-time 빈닝 lazy 경로: 해당 빈 범위의 raw m/z 평균
            lo = float(self._bin_edges[channel_idx])
            hi = float(self._bin_edges[channel_idx + 1])
            for i, (x, y, *_) in enumerate(self._parser.coordinates):
                mzs, intensities = self._parser.getspectrum(i)
                mzs_arr = np.asarray(mzs, dtype=np.float64)
                ints_arr = np.asarray(intensities, dtype=np.float32)
                mask = (mzs_arr >= lo) & (mzs_arr < hi)
                if mask.any():
                    img[y - 1, x - 1] = float(ints_arr[mask].mean())
        else:
            # 원본 lazy 경로: 가장 가까운 m/z 값 사용
            target_mz = self.mz_array[channel_idx]
            for i, (x, y, *_) in enumerate(self._parser.coordinates):
                mzs, intensities = self._parser.getspectrum(i)
                mzs_arr = np.asarray(mzs, dtype=np.float64)
                nearest = int(np.argmin(np.abs(mzs_arr - target_mz)))
                img[y - 1, x - 1] = intensities[nearest]

        return img

    def _apply_normalization(self, img: np.ndarray) -> np.ndarray:
        if self.norm_mode == "none" or self._tic_map is None:
            return img

        if self.norm_mode == "tic":
            coeff = self._tic_map
        elif self.norm_mode == "rms":
            coeff = self._get_rms_map()
        elif self.norm_mode == "median":
            coeff = self._get_median_map()
        else:
            return img

        safe = np.where(coeff > 0, coeff, 1.0)
        return img / safe

    # ------------------------------------------------------------------ #
    #  정규화 계수 맵 (lazy 캐시)
    # ------------------------------------------------------------------ #

    def _compute_tic_map(self) -> None:
        """TIC 맵(픽셀별 intensity 합산)을 계산해 캐시한다."""
        if self._cube is not None:
            self._tic_map = self._cube.sum(axis=2, dtype=np.float64).astype(np.float32)
        else:
            H, W = self.shape
            tic = np.zeros((H, W), dtype=np.float32)
            for idx, (x, y, *_) in enumerate(self._parser.coordinates):
                _, intensities = self._parser.getspectrum(idx)
                tic[y - 1, x - 1] = float(np.sum(intensities))
            self._tic_map = tic

    def _get_rms_map(self) -> np.ndarray:
        if self._rms_map is None:
            if self._full_loaded:
                self._rms_map = np.sqrt(
                    np.mean(self._cube.astype(np.float64) ** 2, axis=2)
                ).astype(np.float32)
            else:
                H, W = self.shape
                rms = np.zeros((H, W), dtype=np.float32)
                for idx, (x, y, *_) in enumerate(self._parser.coordinates):
                    _, intensities = self._parser.getspectrum(idx)
                    rms[y - 1, x - 1] = float(np.sqrt(np.mean(np.asarray(intensities) ** 2)))
                self._rms_map = rms
        return self._rms_map

    def _get_median_map(self) -> np.ndarray:
        if self._median_map is None:
            if self._full_loaded:
                self._median_map = np.median(self._cube, axis=2).astype(np.float32)
            else:
                H, W = self.shape
                med = np.zeros((H, W), dtype=np.float32)
                for idx, (x, y, *_) in enumerate(self._parser.coordinates):
                    _, intensities = self._parser.getspectrum(idx)
                    med[y - 1, x - 1] = float(np.median(intensities))
                self._median_map = med
        return self._median_map

    # ------------------------------------------------------------------ #
    #  스펙트럼 반환
    # ------------------------------------------------------------------ #

    def get_global_spectrum(self) -> np.ndarray:
        """모든 픽셀의 intensity 합산 스펙트럼 (N,) float64를 반환한다."""
        if self._global_spectrum is not None:
            return self._global_spectrum

        if self._full_loaded:
            self._global_spectrum = self._cube.sum(axis=(0, 1), dtype=np.float64)
        else:
            spectrum = np.zeros(self.n_channels, dtype=np.float64)
            for idx, (x, y, *_) in enumerate(self._parser.coordinates):
                mzs, intensities = self._parser.getspectrum(idx)
                if self.mode == "continuous" and self._bin_edges is None:
                    spectrum += np.asarray(intensities, dtype=np.float64)
                elif self._bin_edges is not None:
                    # load-time 빈닝 lazy: 빈별로 누적
                    pix_idx = np.clip(
                        np.digitize(mzs, self._bin_edges) - 1, 0, self.n_channels - 1
                    )
                    np.add.at(spectrum, pix_idx, np.asarray(intensities, dtype=np.float64))
                else:
                    indices = np.searchsorted(self.mz_array, mzs)
                    indices = np.clip(indices, 0, self.n_channels - 1)
                    spectrum[indices] += np.asarray(intensities, dtype=np.float64)
            self._global_spectrum = spectrum

        return self._global_spectrum

    def get_pixel_spectrum(self, row: int, col: int):
        """
        특정 픽셀(row, col)의 (mz_array, intensities) 튜플을 반환한다.
        row, col은 0-based.
        """
        H, W = self.shape
        row = int(np.clip(row, 0, H - 1))
        col = int(np.clip(col, 0, W - 1))

        if self._full_loaded:
            intensities = self._cube[row, col, :].astype(np.float64)
        else:
            x, y = col + 1, row + 1
            if not hasattr(self, "_coord_to_idx"):
                self._coord_to_idx = {
                    (cx, cy): i for i, (cx, cy, *_) in enumerate(self._parser.coordinates)
                }
            idx = self._coord_to_idx.get((x, y))
            if idx is None:
                return self.mz_array, np.zeros(self.n_channels, dtype=np.float64)

            raw_mzs, raw_ints = self._parser.getspectrum(idx)

            if self._bin_edges is not None:
                # load-time 빈닝 lazy: 빈별 평균 재구성
                pix_bin_idx = np.clip(
                    np.digitize(raw_mzs, self._bin_edges) - 1, 0, self.n_channels - 1
                )
                binned = np.zeros(self.n_channels, dtype=np.float64)
                np.add.at(binned, pix_bin_idx, np.asarray(raw_ints, dtype=np.float64))
                counts = np.bincount(pix_bin_idx, minlength=self.n_channels).astype(np.float64)
                safe = np.where(counts > 0, counts, 1.0)
                intensities = binned / safe
            else:
                intensities = np.asarray(raw_ints, dtype=np.float64)

        return self.mz_array, intensities

    def get_roi_spectrum(self, r0: int, r1: int, c0: int, c1: int):
        """
        박스(r0..r1, c0..c1, 0-based 포함 범위) 내부 픽셀들의 평균 스펙트럼을
        (mz_array, mean_intensity) 튜플로 반환한다.
        get_pixel_spectrum()과 동일하게 정규화는 적용하지 않은 raw 값을 반환한다.
        """
        H, W = self.shape
        r0 = int(np.clip(r0, 0, H - 1))
        r1 = int(np.clip(r1, 0, H - 1))
        c0 = int(np.clip(c0, 0, W - 1))
        c1 = int(np.clip(c1, 0, W - 1))
        if r1 < r0:
            r0, r1 = r1, r0
        if c1 < c0:
            c0, c1 = c1, c0

        if self._full_loaded:
            box = self._cube[r0:r1 + 1, c0:c1 + 1, :].astype(np.float64)
            mean_intensity = box.mean(axis=(0, 1))
            return self.mz_array, mean_intensity

        # ── lazy 모드: 박스 내부 좌표만 필터링해 픽셀별 스펙트럼 누적 후 평균 ──
        total = np.zeros(self.n_channels, dtype=np.float64)
        count = 0
        for i, (x, y, *_) in enumerate(self._parser.coordinates):
            row, col = y - 1, x - 1
            if not (r0 <= row <= r1 and c0 <= col <= c1):
                continue
            raw_mzs, raw_ints = self._parser.getspectrum(i)

            if self._bin_edges is not None:
                pix_bin_idx = np.clip(
                    np.digitize(raw_mzs, self._bin_edges) - 1, 0, self.n_channels - 1
                )
                binned = np.zeros(self.n_channels, dtype=np.float64)
                np.add.at(binned, pix_bin_idx, np.asarray(raw_ints, dtype=np.float64))
                counts = np.bincount(pix_bin_idx, minlength=self.n_channels).astype(np.float64)
                safe = np.where(counts > 0, counts, 1.0)
                pixel_spectrum = binned / safe
            else:
                pixel_spectrum = np.asarray(raw_ints, dtype=np.float64)

            total += pixel_spectrum
            count += 1

        if count == 0:
            return self.mz_array, np.zeros(self.n_channels, dtype=np.float64)

        # full-load cube에서는 측정 좌표가 없는 칸도 0인 픽셀로 평균에 포함된다.
        # 같은 직사각형이 파일 크기에 따라 다른 값을 내지 않도록 lazy 경로도
        # ROI의 기하학적 픽셀 수를 분모로 사용한다.
        roi_pixel_count = (r1 - r0 + 1) * (c1 - c0 + 1)
        return self.mz_array, total / roi_pixel_count

    def get_bin_image(self, channel_idx: int, bin_da: float, mode: str = "mean") -> np.ndarray:
        """
        view-time 빈닝: channel_idx 채널의 m/z를 중심으로
        ±(bin_da/2) 범위 내 채널을 집계(mean/sum)하여 반환한다.
        load-time 빈닝과 독립적으로 동작한다.
        """
        if bin_da <= 0:
            return self.get_channel_image(channel_idx)

        mz_c = self.mz_at(channel_idx)
        mask = np.abs(self.mz_array - mz_c) <= bin_da / 2.0
        indices = np.where(mask)[0]

        if len(indices) == 0:
            return self.get_channel_image(channel_idx)
        if len(indices) == 1:
            return self.get_channel_image(int(indices[0]))

        stack = np.stack([self.get_channel_image(int(i)) for i in indices], axis=0)
        if mode == "sum":
            return stack.sum(axis=0).astype(np.float32)
        return stack.mean(axis=0).astype(np.float32)

    def get_tic_image(self) -> np.ndarray:
        """TIC 이미지 (H, W)를 반환한다."""
        if self._tic_map is None:
            self._compute_tic_map()
        return self._tic_map.copy()

    # ------------------------------------------------------------------ #
    #  정규화 모드 변경
    # ------------------------------------------------------------------ #

    def set_normalization(self, mode: str) -> None:
        allowed = ("none", "tic", "rms", "median")
        if mode not in allowed:
            raise ValueError(f"Normalization mode must be one of {allowed}.")
        self.norm_mode = mode

    # ------------------------------------------------------------------ #
    #  유틸
    # ------------------------------------------------------------------ #

    def pixel_size_nm(self) -> float | None:
        """픽셀 크기(nm/pixel)를 반환한다. 메타데이터가 없으면 None."""
        if self.mode == "tiff":
            return self._tiff_pixel_size_nm
        if self._parser is None:
            return None
        try:
            return float(self._parser.imzmldict["pixel size x"])
        except (KeyError, TypeError):
            return None

    def is_loaded(self) -> bool:
        return self._parser is not None or self._cube is not None

    def mz_at(self, channel_idx: int) -> float:
        return float(self.mz_array[int(channel_idx)])

    def nearest_channel(self, mz_value: float) -> int:
        return int(np.argmin(np.abs(self.mz_array - mz_value)))
